from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.ai.cover_letter_generator import CoverLetterDraft
from backend.app.ai.question_agent import QuestionAnswer
from backend.app.ai.question_extractor import ScreeningQuestion
from backend.app.ai.resume_tailor import TailoredResume
from backend.app.db.database import get_db
from backend.app.models.application import (
    ApplicationContentUpdate,
    ApplicationListResponse,
    ApplicationResponse,
    SubmissionResult,
)
from backend.app.services.application_service import application_service

router = APIRouter(prefix="/applications", tags=["Applications"])


class PrepareApplicationRequest(BaseModel):
    resume_file_path: Optional[str] = Field(default=None, description="Path to specific resume version on disk")


class CoverLetterGenerateRequest(BaseModel):
    tone: str = Field(default="professional", description="Tone for the cover letter: professional, enthusiastic, concise")


class AnswerQuestionsRequest(BaseModel):
    questions: Optional[List[ScreeningQuestion]] = Field(default=None, description="Optional custom questions to answer")


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


@router.post("/{application_id}/extract-questions", response_model=List[ScreeningQuestion], status_code=status.HTTP_200_OK)
async def extract_questions(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Phase 32: Extract screening questions from the application page."""
    return await application_service.extract_screening_questions(db, application_id)


@router.post("/{application_id}/answer-questions", response_model=List[QuestionAnswer], status_code=status.HTTP_200_OK)
def answer_questions(
    application_id: int,
    request: Optional[AnswerQuestionsRequest] = None,
    db: Session = Depends(get_db)
):
    """Phase 33: Generate grounded, zero-hallucination answers for screening questions."""
    custom_qs = request.questions if request else None
    return application_service.answer_screening_questions(db, application_id, custom_qs)


@router.post("/{application_id}/tailor-resume", response_model=TailoredResume, status_code=status.HTTP_200_OK)
def tailor_resume(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Phase 34: Generate job-specific tailored resume draft with verified factual integrity."""
    return application_service.generate_tailored_resume(db, application_id)


@router.post("/{application_id}/cover-letter", response_model=CoverLetterDraft, status_code=status.HTTP_200_OK)
def generate_cover_letter(
    application_id: int,
    request: Optional[CoverLetterGenerateRequest] = None,
    db: Session = Depends(get_db)
):
    """Phase 35: Generate grounded, role-specific cover letter draft."""
    tone = request.tone if request else "professional"
    return application_service.generate_cover_letter(db, application_id, tone)


@router.patch("/{application_id}", response_model=ApplicationResponse, status_code=status.HTTP_200_OK)
def update_application_content(
    application_id: int,
    update_data: ApplicationContentUpdate,
    db: Session = Depends(get_db)
):
    """Phase 35 & 37: Allow user editing of filled fields, cover letter, answers, tailored resume, or status."""
    app_record = application_service.update_application_content(db, application_id, update_data)
    return ApplicationResponse.model_validate(app_record)


@router.post("/{application_id}/approve", response_model=ApplicationResponse, status_code=status.HTTP_200_OK)
def approve_application(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Phase 37: Explicit Human-in-the-Loop Approval Action."""
    app_record = application_service.approve_application(db, application_id)
    return ApplicationResponse.model_validate(app_record)


@router.post("/{application_id}/submit", response_model=SubmissionResult, status_code=status.HTTP_200_OK)
async def submit_application(
    application_id: int,
    request: Optional[PrepareApplicationRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Phase 38: Final submission step through browser workflow.
    Phase 39: Validation error detection, failure recovery, and loop prevention.
    MANDATORY SAFETY INVARIANT: Only APPROVED applications can reach submission.
    """
    resume_path = request.resume_file_path if request else None
    return await application_service.submit_application(
        db=db,
        app_id=application_id,
        resume_file_path=resume_path
    )
