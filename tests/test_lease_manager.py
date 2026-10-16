import asyncio
import tempfile
from pathlib import Path
import pytest

from src.knowledge.lease_manager import ReaderLeaseManager
from src.knowledge.workspace_manager import TenantWorkspaceManager


def test_reader_lease_basic_counting():
    async def _run():
        mgr = ReaderLeaseManager()
        tenant = "t1"
        proj = "p1"
        ver = "rev_1"

        assert await mgr.get_active_count(tenant, proj, ver) == 0

        async with mgr.lease(tenant, proj, ver):
            assert await mgr.get_active_count(tenant, proj, ver) == 1
            async with mgr.lease(tenant, proj, ver):
                assert await mgr.get_active_count(tenant, proj, ver) == 2
            assert await mgr.get_active_count(tenant, proj, ver) == 1

        assert await mgr.get_active_count(tenant, proj, ver) == 0

    asyncio.run(_run())


def test_reader_lease_concurrent_drain():
    async def _run():
        mgr = ReaderLeaseManager(default_drain_timeout_seconds=5.0)
        tenant = "t1"
        proj = "p1"
        v1 = "rev_1"
        v2 = "rev_2"

        cleaned_up = []

        def cleanup_cb(inst):
            cleaned_up.append(inst)

        # 1. Start 3 slow workers holding v1 lease
        started_workers = asyncio.Event()
        finish_workers = asyncio.Event()
        worker_count = 3
        entered = 0

        async def worker(idx):
            nonlocal entered
            async with mgr.lease(tenant, proj, v1):
                entered += 1
                if entered == worker_count:
                    started_workers.set()
                await finish_workers.wait()

        tasks = [asyncio.create_task(worker(i)) for i in range(worker_count)]
        await started_workers.wait()

        assert await mgr.get_active_count(tenant, proj, v1) == 3

        # 2. Retire v1 while queries are in-flight
        dummy_instance_v1 = {"version": "v1_engine"}
        await mgr.mark_retired(
            tenant, proj, v1, dummy_instance_v1, cleanup_callback=cleanup_cb
        )

        # 3. New queries acquire v2 without interference
        async with mgr.lease(tenant, proj, v2):
            assert await mgr.get_active_count(tenant, proj, v2) == 1
            # v1 cleanup should NOT have happened yet because leases > 0
            assert len(cleaned_up) == 0

        # 4. Finish all v1 workers
        finish_workers.set()
        await asyncio.gather(*tasks)

        # Wait for drain background task to finish
        await mgr.wait_all_drains()

        # 5. Verify v1 is completely drained and cleaned up
        assert await mgr.get_active_count(tenant, proj, v1) == 0
        assert len(cleaned_up) == 1
        assert cleaned_up[0]["version"] == "v1_engine"

    asyncio.run(_run())


def test_workspace_manager_lease_integration():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            ws_mgr = TenantWorkspaceManager(Path(tmpdir))
            tenant = "tenant_alpha"
            proj = "project_beta"

            # Check initial version
            active_dir = ws_mgr.get_active_dir(tenant, proj)
            assert active_dir.resolve().name == "rev_1"

            # Acquire read lease
            async with ws_mgr.acquire_read_lease(tenant, proj) as rag:
                assert rag is not None
                # Check active leases on rev_1
                count = await ws_mgr.lease_mgr.get_active_count(tenant, proj, "rev_1")
                assert count == 1

            # Lease released
            count_after = await ws_mgr.lease_mgr.get_active_count(tenant, proj, "rev_1")
            assert count_after == 0

    asyncio.run(_run())
