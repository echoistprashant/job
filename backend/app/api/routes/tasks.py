from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from backend.app.core.task_runner import TaskInfo, task_runner

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=List[TaskInfo], status_code=status.HTTP_200_OK)
def list_tasks(limit: int = Query(20, ge=1, le=100)):
    """List recent background tasks and their current execution state."""
    return task_runner.list_tasks(limit=limit)


@router.get("/{task_id}", response_model=TaskInfo, status_code=status.HTTP_200_OK)
def get_task_status(task_id: str):
    """Retrieve the status, progress, and result of an asynchronous background task."""
    task = task_runner.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found."
        )
    return task
