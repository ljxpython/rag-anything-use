"""Single supervisor, isolated builder process group, explicit interrupted attempts."""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import signal
import sys
from pathlib import Path

from src.knowledge.generations import KnowledgeGenerationService
from src.knowledge.jobs import KnowledgeJobStore
from src.knowledge.upload_service import safe_error

logger = logging.getLogger(__name__)


class KnowledgeJobSupervisor:
    def __init__(self, store, generations):
        self.store, self.generations = store, generations
        self._task = None
        self._child = None
        self._owner = None
        self._stopping = False

    def _lock(self, name):
        handle = (self.store.path.parent / name).open("a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            handle.close()
            return None

    async def start(self):
        self._owner = self._lock(".supervisor.lock")
        if self._owner is None:
            return False
        try:
            # A dead supervisor's builder retains flock until its stdin watchdog exits.
            async with asyncio.timeout(30):
                while (builder := self._lock(".builder.lock")) is None:
                    await asyncio.sleep(0.1)
        except BaseException:
            self._owner.close()
            self._owner = None
            raise
        builder.close()
        await asyncio.to_thread(self.store.recover)
        from src.knowledge.upload_service import KnowledgeUploadService

        await asyncio.to_thread(KnowledgeUploadService(self.store).cleanup_uploads)
        self._stopping = False
        self._task = asyncio.create_task(self._run())
        return True

    async def _run(self):
        while not self._stopping:
            job_id = await asyncio.to_thread(self.store.next_job)
            if not job_id:
                await asyncio.sleep(0.2)
                continue
            builder = self._lock(".builder.lock")
            if builder is None:
                await asyncio.sleep(0.2)
                continue
            try:
                await self.process(job_id, builder)
            except asyncio.CancelledError:
                await self._stop_child()
                self.store.update_job(
                    job_id, "failed", "knowledge_processing_interrupted"
                )
                raise
            except TimeoutError:
                self.store.update_job(job_id, "failed", "knowledge_processing_timeout")
            except Exception as exc:
                logger.warning("knowledge_worker_failed: %s", type(exc).__name__)
                await asyncio.to_thread(
                    self.store.update_job, job_id, "failed", safe_error(exc)
                )
            finally:
                builder.close()

    async def process(self, job_id, builder_lock):
        job = await asyncio.to_thread(self.store.get_job, job_id)
        if (
            not self.store.config.online_enabled
            or not self.store.project(job["kb"])["enabled"]
        ):
            # queued survives an administrator pause.
            await asyncio.sleep(0.2)
            return
        scope = self.generations.scope(job["kb"])
        await asyncio.to_thread(self.store.update_job, job_id, "parsing")
        config = self.store.config
        started = asyncio.get_running_loop().time()
        async with asyncio.timeout(config.job_timeout_seconds):
            await self.generations.authorizer.authorize(
                scope, "start", json.loads(job["identity"]), {"job_id": job_id}
            )
        log_path = self.store.path.parent / "builder.log"
        with log_path.open("a") as log:
            # The inherited flock remains held until every builder process exits.
            self._child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "src.knowledge.job_worker",
                str(self.store.path),
                job_id,
                str(builder_lock.fileno()),
                stdin=asyncio.subprocess.PIPE,
                stdout=log,
                stderr=log,
                start_new_session=True,
                pass_fds=(builder_lock.fileno(),),
                cwd=Path(__file__).resolve().parents[2],
                env={
                    **os.environ,
                    "OMP_NUM_THREADS": os.getenv("KNOWLEDGE_BUILDER_MAX_THREADS", "2"),
                    "MKL_NUM_THREADS": os.getenv("KNOWLEDGE_BUILDER_MAX_THREADS", "2"),
                    "OPENBLAS_NUM_THREADS": os.getenv("KNOWLEDGE_BUILDER_MAX_THREADS", "2"),
                    "VECLIB_MAXIMUM_THREADS": os.getenv("KNOWLEDGE_BUILDER_MAX_THREADS", "2"),
                    "NUMEXPR_NUM_THREADS": os.getenv("KNOWLEDGE_BUILDER_MAX_THREADS", "2"),
                    "KNOWLEDGE_ROOT_DIR": str(config.root_dir.expanduser().resolve()),
                    "KNOWLEDGE_BUILDER_ROOT": str(
                        config.root_dir.expanduser().resolve()
                    ),
                    "KNOWLEDGE_BUILDER_CONFIG": json.dumps(
                        {
                            key: value
                            for key, value in vars(config).items()
                            if key not in {"root_dir", "authorization_secret"}
                        }
                    ),
                },
            )
        try:
            async with asyncio.timeout(
                max(
                    0.01,
                    config.job_timeout_seconds
                    - (asyncio.get_running_loop().time() - started),
                )
            ):
                code = await self._child.wait()
                if code != 0 or self.store.get_job(job_id)["status"] != "publishing":
                    raise ValueError("knowledge_processing_failed")
                await self.generations.activate(job_id)
        except TimeoutError:
            await self._stop_child()
            self.store.update_job(job_id, "failed", "knowledge_processing_timeout")
        except asyncio.CancelledError:
            await self._stop_child()
            self.store.update_job(job_id, "failed", "knowledge_processing_interrupted")
            raise
        finally:
            await self._stop_child()

    async def _stop_child(self):
        child, self._child = self._child, None
        if child is None:
            return
        # This PID is our own unreaped child; never signal an arbitrary persisted PID.
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if child.returncode is None:
            try:
                async with asyncio.timeout(5):
                    await child.wait()
            except TimeoutError:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await child.wait()
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if child.stdin:
            child.stdin.close()

    async def stop(self):
        self._stopping = True
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await self._stop_child()
        if self._owner:
            self._owner.close()
            self._owner = None


async def _build_child(database_path, job_id, lock_fd):
    try:
        os.nice(int(os.getenv("KNOWLEDGE_BUILDER_NICE", "10")))
    except (AttributeError, OSError, ValueError):
        pass

    from src.knowledge.config import build_knowledge_service_config

    config = build_knowledge_service_config()
    from dataclasses import replace

    config = replace(
        config,
        root_dir=Path(os.environ["KNOWLEDGE_BUILDER_ROOT"]),
        **json.loads(os.getenv("KNOWLEDGE_BUILDER_CONFIG", "{}")),
    )
    store = KnowledgeJobStore(config)
    if store.path.resolve() != Path(database_path).resolve():
        raise ValueError("knowledge_path_escape")
    fcntl.flock(int(lock_fd), fcntl.LOCK_EX | fcntl.LOCK_NB)

    async def parent_watch():
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_running_loop().connect_read_pipe(
            lambda: protocol, sys.stdin.buffer
        )
        await reader.read(1)
        os.killpg(os.getpgrp(), signal.SIGTERM)

    watcher = asyncio.create_task(parent_watch())
    generations = KnowledgeGenerationService(store)
    logging.getLogger("lightrag").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        await generations.build(job_id)
    except Exception as exc:
        store.update_job(job_id, "failed", safe_error(exc))
        logger.exception("knowledge_builder_failed: %s", exc)
        raise
    finally:
        watcher.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(_build_child(*sys.argv[1:]))
    except BaseException:
        os._exit(1)
    os._exit(0)
