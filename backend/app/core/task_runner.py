import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskInfo(BaseModel):
    task_id: str
    name: str
    status: str = "PENDING"  # PENDING, RUNNING, SUCCESS, FAILED
    progress: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskRunner:
    """
    Phase 42: In-process asynchronous task runner.
    Provides non-blocking execution of long-running tasks (job searches, scheduled workflows)
    with status polling, error isolation, and progress tracking.
    """

    def __init__(self):
        self._tasks: Dict[str, TaskInfo] = {}
        self._running_async_tasks: Dict[str, asyncio.Task] = {}

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """Retrieve task information by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> List[TaskInfo]:
        """List recently submitted tasks."""
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def update_progress(self, task_id: str, progress: int):
        """Update progress percentage for a running task."""
        if task_id in self._tasks:
            self._tasks[task_id].progress = max(0, min(100, progress))

    def submit_task(
        self,
        name: str,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        **kwargs
    ) -> str:
        """
        Submit a coroutine for asynchronous background execution.
        Returns unique task_id immediately.
        """
        task_id = str(uuid.uuid4())
        info = TaskInfo(task_id=task_id, name=name)
        self._tasks[task_id] = info

        async def _wrapper():
            info.status = "RUNNING"
            info.started_at = datetime.now(timezone.utc)
            logger.info(f"[TaskRunner] Task {task_id} ({name}) started.")
            try:
                res = await coro_fn(*args, **kwargs)
                info.status = "SUCCESS"
                info.progress = 100
                info.result = res
                logger.info(f"[TaskRunner] Task {task_id} ({name}) completed successfully.")
            except Exception as exc:
                info.status = "FAILED"
                info.error = str(exc)
                logger.error(f"[TaskRunner] Task {task_id} ({name}) failed: {exc}", exc_info=True)
            finally:
                info.completed_at = datetime.now(timezone.utc)
                self._running_async_tasks.pop(task_id, None)

        try:
            loop = asyncio.get_running_loop()
            async_task = loop.create_task(_wrapper())
            self._running_async_tasks[task_id] = async_task
        except RuntimeError:
            logger.warning(f"[TaskRunner] No running asyncio loop found when submitting {name}.")

        return task_id


task_runner = TaskRunner()
