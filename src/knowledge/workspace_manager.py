import asyncio
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, Tuple

from lightrag import LightRAG

from src.knowledge.lease_manager import ReaderLeaseManager
from src.knowledge.llm_client import (
    create_lightrag_embedding_func,
    unified_llm_func,
)


class TenantWorkspaceManager:
    """Enterprise multi-tenant workspace manager with zero-lock POSIX CAS activation and reader leases."""

    def __init__(
        self,
        storage_root: Path,
        lease_manager: Optional[ReaderLeaseManager] = None,
    ):
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        # Key: "tenant_id:project_id" -> LightRAG instance
        self._rag_instances: Dict[str, LightRAG] = {}
        # Key: "tenant_id:project_id" -> current version name (e.g. "rev_1")
        self._active_versions: Dict[str, str] = {}
        self.lease_mgr = lease_manager or ReaderLeaseManager()
        self._lock = asyncio.Lock()

    def get_project_dir(self, tenant_id: str, project_id: str) -> Path:
        p_dir = self.storage_root / tenant_id / project_id
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir

    def get_active_version_name(self, tenant_id: str, project_id: str) -> str:
        """Resolves the current active version folder name."""
        active_symlink = self.get_project_dir(tenant_id, project_id) / "active"
        if not active_symlink.exists():
            return "rev_1"
        try:
            target = active_symlink.resolve()
            return target.name
        except Exception:
            return "rev_1"

    def get_active_dir(self, tenant_id: str, project_id: str) -> Path:
        """Returns the active working directory, initializing rev_1 symlink if not present."""
        p_dir = self.get_project_dir(tenant_id, project_id)
        active_symlink = p_dir / "active"
        if not active_symlink.exists():
            rev_1 = p_dir / "revisions" / "rev_1"
            rev_1.mkdir(parents=True, exist_ok=True)
            active_symlink.symlink_to(
                Path("revisions") / "rev_1", target_is_directory=True
            )
        return active_symlink

    async def get_rag_engine(
        self,
        tenant_id: str = "__default",
        project_id: str = "11111111-1111-4111-8111-111111111111",
    ) -> Tuple[LightRAG, str]:
        """Returns initialized LightRAG engine and active version name."""
        key = f"{tenant_id}:{project_id}"
        async with self._lock:
            current_version = self.get_active_version_name(tenant_id, project_id)
            if key not in self._rag_instances or self._active_versions.get(key) != current_version:
                active_dir = self.get_active_dir(tenant_id, project_id)
                rag = LightRAG(
                    working_dir=str(active_dir),
                    llm_model_func=unified_llm_func,
                    embedding_func=create_lightrag_embedding_func(),
                )
                await rag.initialize_storages()
                self._rag_instances[key] = rag
                self._active_versions[key] = current_version
            return self._rag_instances[key], self._active_versions[key]

    @asynccontextmanager
    async def acquire_read_lease(
        self, tenant_id: str, project_id: str
    ) -> AsyncGenerator[LightRAG, None]:
        """Acquires a versioned reader lease on the active engine to prevent abrupt teardown during queries."""
        rag, version_tag = await self.get_rag_engine(tenant_id, project_id)
        async with self.lease_mgr.lease(tenant_id, project_id, version_tag):
            yield rag

    async def atomic_publish_candidate(
        self, tenant_id: str, project_id: str, candidate_dir: Path
    ) -> int:
        """Publishes candidate build directory as the next revision using POSIX atomic symlink swap."""
        p_dir = self.get_project_dir(tenant_id, project_id)
        revisions_dir = p_dir / "revisions"
        revisions_dir.mkdir(parents=True, exist_ok=True)

        existing_revs = [
            int(d.name.split("_")[1])
            for d in revisions_dir.glob("rev_*")
            if d.is_dir() and d.name.split("_")[-1].isdigit()
        ]
        next_rev_num = (max(existing_revs) + 1) if existing_revs else 1
        target_rev_dir = revisions_dir / f"rev_{next_rev_num}"

        # Move candidate to revisions directory
        shutil.move(str(candidate_dir), str(target_rev_dir))

        # Linux POSIX Atomic Symlink Swap:
        # ln -sfn revisions/rev_<next> active.tmp && mv -T active.tmp active
        active_symlink = p_dir / "active"
        tmp_symlink = p_dir / "active.tmp"
        rel_target = Path("revisions") / f"rev_{next_rev_num}"

        if tmp_symlink.is_symlink() or tmp_symlink.exists():
            tmp_symlink.unlink()
        tmp_symlink.symlink_to(rel_target, target_is_directory=True)

        # os.replace performs atomic rename on POSIX
        os.replace(str(tmp_symlink), str(active_symlink))

        key = f"{tenant_id}:{project_id}"
        async with self._lock:
            old_version = self._active_versions.pop(key, None)
            old_rag = self._rag_instances.pop(key, None)

        if old_rag is not None and old_version is not None:
            # Launch non-blocking graceful drain for the retired version
            await self.lease_mgr.mark_retired(
                tenant_id, project_id, old_version, old_rag
            )

        return next_rev_num
