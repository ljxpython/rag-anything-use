import asyncio
import os
import signal
import sys
import subprocess
import time

import pytest

from src.knowledge.job_worker import KnowledgeJobSupervisor


def test_single_supervisor_preserves_queued_and_recovers(online_services):
    from test_knowledge_generations import upload

    s = online_services

    async def run():
        receipt = await upload(s, "text", "a")
        first = KnowledgeJobSupervisor(s.store, s.generations)
        second = KnowledgeJobSupervisor(s.store, s.generations)

        async def idle():
            await asyncio.Event().wait()

        first._run = idle
        second._run = idle
        assert await first.start()
        assert not await second.start()
        await first.stop()
        assert s.store.get_job(receipt["job_id"])["status"] == "queued"
        s.store.update_job(receipt["job_id"], "indexing")
        assert await second.start()
        assert s.store.get_job(receipt["job_id"])["status"] == "failed"
        await second.stop()

    asyncio.run(run())


def test_restart_waits_for_orphan_builder_before_recovery(online_services):
    from test_knowledge_generations import upload

    s = online_services
    supervisor = KnowledgeJobSupervisor(s.store, s.generations)

    async def run():
        receipt = await upload(s, "interrupted builder", "a")
        s.store.update_job(receipt["job_id"], "indexing")
        held = supervisor._lock(".builder.lock")

        async def idle():
            await asyncio.Event().wait()

        supervisor._run = idle
        starting = asyncio.create_task(supervisor.start())
        try:
            await asyncio.sleep(0.05)
            assert not starting.done()
            assert s.store.get_job(receipt["job_id"])["status"] == "indexing"
            held.close()
            assert await starting
            assert s.store.get_job(receipt["job_id"])["status"] == "failed"
        finally:
            if not held.closed:
                held.close()
            await supervisor.stop()

    asyncio.run(run())


def test_actual_supervisor_sigkill_stdin_watchdog_and_restart(
    online_services, tmp_path
):
    from test_knowledge_generations import upload

    s = online_services
    receipt = asyncio.run(upload(s, "parent death", "a"))
    marker = tmp_path / "builder-pid"
    child_code = """
import asyncio, os, sys
from pathlib import Path
from src.knowledge.job_worker import _build_child, KnowledgeGenerationService
async def paused(self, job_id):
    Path(sys.argv[4]).write_text(str(os.getpid()))
    await asyncio.Event().wait()
KnowledgeGenerationService.build = paused
asyncio.run(_build_child(*sys.argv[1:4]))
"""
    parent_code = """
import asyncio, sys
from pathlib import Path
from types import SimpleNamespace
from src.knowledge.config import KnowledgeServiceConfig
from src.knowledge.jobs import KnowledgeJobStore
from src.knowledge.job_worker import KnowledgeJobSupervisor
config = KnowledgeServiceConfig(root_dir=Path(sys.argv[1]), online_enabled=True)
store = KnowledgeJobStore(config)
class Allow:
    async def authorize(self, *args):
        return None
generations = SimpleNamespace(scope=lambda kb: None, authorizer=Allow())
supervisor = KnowledgeJobSupervisor(store, generations)
original = asyncio.create_subprocess_exec
async def spawn(*args, **kwargs):
    child = await original(sys.executable, '-c', sys.argv[4], args[3], args[4], args[5], sys.argv[3], **kwargs)
    Path(sys.argv[3] + '.spawned').write_text(str(child.pid))
    return child
asyncio.create_subprocess_exec = spawn
async def run():
    assert await supervisor.start()
    await supervisor._task
asyncio.run(run())
"""
    parent_log = tmp_path / "supervisor.log"
    log = parent_log.open("w")
    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            parent_code,
            str(s.config.root_dir),
            receipt["job_id"],
            str(marker),
            child_code,
        ],
        stdout=log,
        stderr=log,
    )
    child_pid = None
    supervisor = KnowledgeJobSupervisor(s.store, s.generations)
    try:
        deadline = time.monotonic() + 30
        while not marker.exists() and time.monotonic() < deadline:
            assert parent.poll() is None, parent_log.read_text()
            assert s.store.get_job(receipt["job_id"])["status"] != "failed", (
                s.store.path.parent / "builder.log"
            ).read_text()
            time.sleep(0.05)
        assert marker.exists(), (
            parent_log.read_text() + (s.store.path.parent / "builder.log").read_text()
        )
        child_pid = int(marker.read_text())
        assert s.store.get_job(receipt["job_id"])["status"] == "parsing"
        parent.kill()
        parent.wait(timeout=5)

        async def restart():
            async def idle():
                await asyncio.Event().wait()

            supervisor._run = idle
            async with asyncio.timeout(10):
                assert await supervisor.start()
            assert (
                s.store.get_job(receipt["job_id"])["error_code"]
                == "knowledge_processing_interrupted"
            )
            lock = supervisor._lock(".builder.lock")
            assert lock is not None
            lock.close()
            await supervisor.stop()

        asyncio.run(restart())
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        log.close()
        if child_pid is None and marker.with_suffix(".spawned").exists():
            child_pid = int(marker.with_suffix(".spawned").read_text())
        if child_pid:
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize("action", ["timeout", "cancel", "sigkill"])
def test_actual_child_group_timeout_cancel_and_lock_released(
    online_services, monkeypatch, action
):
    from dataclasses import replace
    from test_knowledge_generations import upload

    s = online_services
    store = type(s.store)(
        replace(s.config, job_timeout_seconds=0.3 if action == "timeout" else 30)
    )
    supervisor = KnowledgeJobSupervisor(store, s.generations)
    original_create = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        # Exercise the supervisor with a real process group and inherited flock.
        return await original_create(
            sys.executable, "-c", "import time; time.sleep(60)", **kwargs
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    async def run():
        receipt = await upload(s, "child test", "a")
        lock = supervisor._lock(".builder.lock")
        task = asyncio.create_task(supervisor.process(receipt["job_id"], lock))
        try:
            if action != "timeout":
                while supervisor._child is None:
                    await asyncio.sleep(0.01)
                pid = supervisor._child.pid
                if action == "cancel":
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                    assert (
                        store.get_job(receipt["job_id"])["error_code"]
                        == "knowledge_processing_interrupted"
                    )
                else:
                    os.killpg(pid, signal.SIGKILL)
                    with pytest.raises(ValueError, match="knowledge_processing_failed"):
                        await task
                    store.recover()
                    assert store.get_job(receipt["job_id"])["status"] == "failed"
                with pytest.raises(ProcessLookupError):
                    os.kill(pid, 0)
            else:
                await task
                assert (
                    store.get_job(receipt["job_id"])["error_code"]
                    == "knowledge_processing_timeout"
                )
            assert supervisor._child is None
        finally:
            lock.close()
        fresh = supervisor._lock(".builder.lock")
        assert fresh is not None
        fresh.close()

    asyncio.run(run())
