from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.app.db.database import get_db
from backend.app.models.application import ApplicationListResponse, ApplicationResponse
from backend.app.services.application_service import application_service

router = APIRouter(prefix="/applications", tags=["Applications"])


class PrepareApplicationRequest(BaseModel):
    resume_file_path: Optional[str] = Field(default=None, description="Path to specific resume version on disk")


@router.post("/{job_id}/prepare", response_model=ApplicationResponse, status_code=status.HTTP_200_OK)
async def prepare_job_application(
    job_id: int,
    request: Optional[PrepareApplicationRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Open application URL in Playwright, semantically autofill form with candidate profile,
    attach resume, and stop strictly before submission, saving draft in READY status.
    """
    resume_path = request.resume_file_path if request else None
    app_record = await application_service.prepare_draft_for_job(
        db=db,
        job_id=job_id,
        resume_file_path=resume_path
    )
    return ApplicationResponse.model_validate(app_record)


@router.get("", response_model=ApplicationListResponse, status_code=status.HTTP_200_OK)
def list_applications(
    status: Optional[str] = Query(None, description="Filter by status: SAVED, MATCHED, READY, APPROVED, SUBMITTED"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List all application drafts and submission tracking records."""
    items, total = application_service.list_applications(
        db=db,
        status_filter=status,
        limit=limit,
        offset=offset
    )
    return ApplicationListResponse(
        total=total,
        items=[ApplicationResponse.model_validate(a) for a in items]
    )


@router.get("/{application_id}", response_model=ApplicationResponse, status_code=status.HTTP_200_OK)
def get_application(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve details for a single application draft."""
    app_record = application_service.get_application(db, application_id)
    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {application_id} not found."
        )
    return ApplicationResponse.model_validate(app_record)
