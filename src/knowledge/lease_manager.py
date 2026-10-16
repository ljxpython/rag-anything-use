import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ReaderLeaseManager:
    """Production-grade reader lease manager for zero-downtime, zero-error hot switching.

    Tracks active read queries per tenant/project/version and gracefully drains
    retired engine instances once their reader leases drop to zero.
    """

    def __init__(self, default_drain_timeout_seconds: float = 30.0):
        self.default_drain_timeout = default_drain_timeout_seconds
        # Key: (tenant_id, project_id, version_tag) -> active reader count
        self._leases: Dict[Tuple[str, str, str], int] = {}
        # Key: (tenant_id, project_id, version_tag) -> retired instance object
        self._draining_instances: Dict[Tuple[str, str, str], Any] = {}
        self._lock = asyncio.Lock()
        self._drain_tasks: set[asyncio.Task] = set()

    async def get_active_count(
        self, tenant_id: str, project_id: str, version_tag: str
    ) -> int:
        """Returns the current number of active queries for a given version."""
        async with self._lock:
            return self._leases.get((tenant_id, project_id, version_tag), 0)

    @asynccontextmanager
    async def lease(
        self, tenant_id: str, project_id: str, version_tag: str
    ) -> AsyncGenerator[None, None]:
        """Context manager to acquire and reliably release a reader lease."""
        key = (tenant_id, project_id, version_tag)
        async with self._lock:
            self._leases[key] = self._leases.get(key, 0) + 1

        try:
            yield
        finally:
            async with self._lock:
                current = self._leases.get(key, 1) - 1
                if current <= 0:
                    self._leases.pop(key, None)
                else:
                    self._leases[key] = current

    async def mark_retired(
        self,
        tenant_id: str,
        project_id: str,
        version_tag: str,
        instance: Any,
        cleanup_callback: Optional[Callable[[Any], Any]] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """Marks a version as retired and launches a graceful drain background task."""
        key = (tenant_id, project_id, version_tag)
        async with self._lock:
            self._draining_instances[key] = instance

        drain_timeout = (
            timeout if timeout is not None else self.default_drain_timeout
        )
        task = asyncio.create_task(
            self._drain_and_cleanup(key, instance, cleanup_callback, drain_timeout)
        )
        self._drain_tasks.add(task)
        task.add_done_callback(self._drain_tasks.discard)

    async def _drain_and_cleanup(
        self,
        key: Tuple[str, str, str],
        instance: Any,
        cleanup_callback: Optional[Callable[[Any], Any]],
        timeout: float,
    ) -> None:
        """Waits for active leases on this key to reach 0, then executes cleanup."""
        tenant_id, project_id, version_tag = key
        poll_interval = 0.1
        max_steps = int(timeout / poll_interval)

        for _ in range(max_steps):
            async with self._lock:
                active = self._leases.get(key, 0)
            if active == 0:
                break
            await asyncio.sleep(poll_interval)

        # Cleanup instance
        async with self._lock:
            self._draining_instances.pop(key, None)

        if cleanup_callback:
            try:
                res = cleanup_callback(instance)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning(
                    f"Cleanup callback for {key} failed: {e}", exc_info=True
                )

        logger.info(
            f"Graceful drain completed for retired version {tenant_id}:{project_id}:{version_tag}"
        )

    async def wait_all_drains(self) -> None:
        """Waits for all in-flight drain tasks to finish (useful during tests or shutdown)."""
        if self._drain_tasks:
            await asyncio.gather(*list(self._drain_tasks), return_exceptions=True)
