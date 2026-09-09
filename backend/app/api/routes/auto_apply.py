from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.ai.auto_apply_rules import AutoApplyPolicy
from backend.app.core.task_runner import task_runner
from backend.app.db.database import get_db, SessionLocal
from backend.app.services.auto_apply_service import AutoApplyCycleReport, auto_apply_service

router = APIRouter(prefix="/auto-apply", tags=["Auto Apply"])


class RunAutoApplyRequest(BaseModel):
    max_jobs: Optional[int] = None
    force_run: bool = False


class QuotaResponse(BaseModel):
    submitted_today: int
    max_per_day: int
    remaining_today: int
    policy_enabled: bool


@router.get("/policy", response_model=AutoApplyPolicy, status_code=status.HTTP_200_OK)
def get_auto_apply_policy():
    """Phase 48: Retrieve reviewable auto-apply rules and safety parameters."""
    return auto_apply_service.get_policy()


@router.post("/policy", response_model=AutoApplyPolicy, status_code=status.HTTP_200_OK)
def update_auto_apply_policy(policy: AutoApplyPolicy):
    """Phase 48: Update auto-apply rules (match threshold, target roles, daily ceiling)."""
    return auto_apply_service.update_policy(policy)


@router.get("/quota", response_model=QuotaResponse, status_code=status.HTTP_200_OK)
def get_daily_quota(db: Session = Depends(get_db)):
    """Phase 49: Check daily submission limits and remaining quota."""
    policy = auto_apply_service.get_policy()
    submitted = auto_apply_service.get_daily_submitted_count(db)
    return QuotaResponse(
        submitted_today=submitted,
        max_per_day=policy.max_applications_per_day,
        remaining_today=max(0, policy.max_applications_per_day - submitted),
        policy_enabled=policy.enabled
    )


@router.post("/run", response_model=AutoApplyCycleReport, status_code=status.HTTP_200_OK)
async def run_auto_apply_now(
    request: Optional[RunAutoApplyRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Phase 49: Run a controlled auto-apply cycle with safety gates and question uncertainty escalations.
    """
    max_jobs = request.max_jobs if request else None
    force_run = request.force_run if request else False

    return await auto_apply_service.run_auto_apply_cycle(
        db=db,
        max_jobs=max_jobs,
        force_run=force_run
    )
