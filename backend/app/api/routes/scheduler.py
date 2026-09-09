from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field
from backend.app.core.scheduler import SchedulerStatusResponse, job_scheduler

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


class IntervalUpdateRequest(BaseModel):
    interval_minutes: int = Field(ge=5, le=1440, description="Schedule interval in minutes (5 to 1440)")


class RunNowResponse(BaseModel):
    status: str
    task_id: str
    message: str


@router.get("/status", response_model=SchedulerStatusResponse, status_code=status.HTTP_200_OK)
def get_scheduler_status():
    """Retrieve recurring scheduler state, interval, last run, next run, and recent history."""
    return job_scheduler.get_status()


@router.post("/start", response_model=SchedulerStatusResponse, status_code=status.HTTP_200_OK)
def start_scheduler():
    """Activate automatic scheduled job discovery."""
    job_scheduler.start()
    return job_scheduler.get_status()


@router.post("/stop", response_model=SchedulerStatusResponse, status_code=status.HTTP_200_OK)
def stop_scheduler():
    """Pause automatic scheduled job discovery."""
    job_scheduler.stop()
    return job_scheduler.get_status()


@router.post("/run-now", response_model=RunNowResponse, status_code=status.HTTP_202_ACCEPTED)
def run_scheduler_now():
    """Trigger an immediate discovery cycle asynchronously in the background."""
    task_id = job_scheduler.trigger_run_now()
    return RunNowResponse(
        status="triggered",
        task_id=task_id,
        message="Discovery cycle triggered in background task runner."
    )


@router.post("/interval", response_model=SchedulerStatusResponse, status_code=status.HTTP_200_OK)
def update_scheduler_interval(request: IntervalUpdateRequest):
    """Update recurring schedule interval in minutes."""
    job_scheduler.set_interval(request.interval_minutes)
    return job_scheduler.get_status()
