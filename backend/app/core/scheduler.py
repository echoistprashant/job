import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.core.task_runner import task_runner
from backend.app.db.database import SessionLocal
from backend.app.services.job_service import job_service

logger = logging.getLogger(__name__)


class SchedulerStatusResponse(BaseModel):
    is_active: bool
    interval_minutes: int
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    total_runs: int = 0
    last_run_result: Optional[Dict[str, Any]] = None
    recent_history: List[Dict[str, Any]] = Field(default_factory=list)


class JobDiscoveryScheduler:
    """
    Phase 43: In-process recurring job discovery scheduler.
    Discovers, normalizes, deduplicates, and matches jobs on a recurring schedule
    without requiring manual user triggers.
    """

    def __init__(self, interval_minutes: int = 60):
        self.is_active: bool = False
        self.interval_minutes: int = interval_minutes
        self.last_run_at: Optional[datetime] = None
        self.next_run_at: Optional[datetime] = None
        self.total_runs: int = 0
        self.last_run_result: Optional[Dict[str, Any]] = None
        self.recent_history: List[Dict[str, Any]] = []
        self._loop_task: Optional[asyncio.Task] = None

    def get_status(self) -> SchedulerStatusResponse:
        return SchedulerStatusResponse(
            is_active=self.is_active,
            interval_minutes=self.interval_minutes,
            last_run_at=self.last_run_at,
            next_run_at=self.next_run_at,
            total_runs=self.total_runs,
            last_run_result=self.last_run_result,
            recent_history=self.recent_history[-10:],
        )

    def start(self):
        """Enable scheduled auto-discovery."""
        if not self.is_active:
            self.is_active = True
            self.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=self.interval_minutes)
            self._ensure_loop_running()
            logger.info(f"[Scheduler] Activated. Next run scheduled at {self.next_run_at.isoformat()}.")

    def stop(self):
        """Pause scheduled auto-discovery."""
        self.is_active = False
        self.next_run_at = None
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None
        logger.info("[Scheduler] Paused.")

    def set_interval(self, minutes: int):
        self.interval_minutes = max(5, minutes)
        if self.is_active:
            self.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=self.interval_minutes)

    def _ensure_loop_running(self):
        if self._loop_task is None or self._loop_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._loop_task = loop.create_task(self._scheduler_loop())
            except RuntimeError:
                logger.warning("[Scheduler] Cannot start scheduler loop without active asyncio loop.")

    async def _scheduler_loop(self):
        while self.is_active:
            try:
                sleep_seconds = self.interval_minutes * 60
                await asyncio.sleep(sleep_seconds)
                if not self.is_active:
                    break
                await self.run_discovery_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Scheduler] Unexpected error in loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def run_discovery_cycle(self) -> Dict[str, Any]:
        """Execute one complete discovery and matching cycle."""
        start_time = datetime.now(timezone.utc)
        logger.info("[Scheduler] Running automated job discovery cycle...")
        result: Dict[str, Any] = {
            "started_at": start_time.isoformat(),
            "status": "in_progress",
            "new_jobs_added": 0,
            "total_jobs_scanned": 0,
        }

        try:
            with SessionLocal() as db:
                new_added, total_scanned = await job_service.collect_and_store_jobs(
                    db=db,
                    keywords=["Software Engineer", "AI Engineer", "Full Stack Developer", "Python"],
                    limit_per_source=25,
                )
                result["new_jobs_added"] = new_added
                result["total_jobs_scanned"] = total_scanned
                result["status"] = "success"
        except Exception as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            logger.error(f"[Scheduler] Discovery cycle failed: {exc}", exc_info=True)

        end_time = datetime.now(timezone.utc)
        result["completed_at"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()

        self.last_run_at = end_time
        self.last_run_result = result
        self.total_runs += 1
        self.recent_history.append(result)
        if self.is_active:
            self.next_run_at = end_time + timedelta(minutes=self.interval_minutes)

        return result

    def trigger_run_now(self) -> str:
        """Trigger an immediate discovery cycle via the async background task runner."""
        return task_runner.submit_task("scheduled_job_discovery", self.run_discovery_cycle)


job_scheduler = JobDiscoveryScheduler(interval_minutes=60)
