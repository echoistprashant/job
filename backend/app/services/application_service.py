from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.agents.application_agent import application_agent
from backend.app.agents.submission_agent import submission_agent
from backend.app.ai.cover_letter_generator import CoverLetterDraft, cover_letter_generator
from backend.app.ai.question_agent import QuestionAnswer, grounded_question_agent
from backend.app.ai.question_extractor import ScreeningQuestion, question_extractor
from backend.app.ai.resume_tailor import TailoredResume, resume_tailor
from backend.app.browser.browser import browser_service
from backend.app.models.application import (
    Application,
    ApplicationContentUpdate,
    ApplicationDraftResult,
    SubmissionResult,
    VALID_STATUSES,
)
from backend.app.models.job import Job
from backend.app.models.resume import CandidateProfile
from backend.app.services.resume_service import resume_service


class ApplicationService:
    async def prepare_draft_for_job(
        self,
        db: Session,
        job_id: int,
        profile: Optional[CandidateProfile] = None,
        resume_file_path: Optional[str] = None
    ) -> Application:
        """
        Orchestrate browser form filling, attachment, and persist draft in READY status.
        """
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found."
            )

        if profile is None:
            profile = resume_service.get_current_profile() or CandidateProfile()

        # Run agent to fill form and stop before submission
        draft_result: ApplicationDraftResult = await application_agent.prepare_application_draft(
            job=job,
            profile=profile,
            resume_file_path=resume_file_path
        )

        # Check for existing application record
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        app_record = db.query(Application).filter(Application.job_id == job_id).first()
        if app_record:
            history = list(app_record.status_history or [])
            if app_record.status != draft_result.status:
                history.append({
                    "from_status": app_record.status,
                    "to_status": draft_result.status,
                    "timestamp": now_iso,
                    "actor": "system",
                    "note": "Draft updated with latest job form details"
                })
                app_record.status_history = history
            app_record.status = draft_result.status
            app_record.filled_fields = draft_result.filled_fields
            app_record.unfilled_fields = draft_result.unfilled_fields
            app_record.application_url = job.url
            app_record.source = job.source
            if draft_result.extracted_questions:
                app_record.screening_questions = draft_result.extracted_questions
            app_record.updated_at = now
            db.commit()
            db.refresh(app_record)
            return app_record

        # Create new application record
        initial_history = [{
            "from_status": None,
            "to_status": draft_result.status,
            "timestamp": now_iso,
            "actor": "system",
            "note": "Application draft initialized"
        }]
        new_app = Application(
            job_id=job_id,
            status=draft_result.status,
            application_url=job.url,
            source=job.source,
            filled_fields=draft_result.filled_fields,
            unfilled_fields=draft_result.unfilled_fields,
            screening_questions=draft_result.extracted_questions,
            answers={},
            status_history=initial_history,
            created_at=now,
            updated_at=now
        )
        db.add(new_app)
        db.commit()
        db.refresh(new_app)
        return new_app

    def list_applications(
        self,
        db: Session,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Application], int]:
        """List application records with optional status filtering and pagination."""
        query = db.query(Application)
        if status_filter:
            query = query.filter(Application.status == status_filter.upper())
        total = query.count()
        items = query.order_by(Application.updated_at.desc()).offset(offset).limit(limit).all()
        return items, total

    def get_application(self, db: Session, app_id: int) -> Optional[Application]:
        """Retrieve single application record by ID."""
        return db.query(Application).filter(Application.id == app_id).first()

    async def extract_screening_questions(
        self,
        db: Session,
        app_id: int
    ) -> List[ScreeningQuestion]:
        """
        Phase 32: Extract screening questions from the application page
        or retrieve previously extracted questions.
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        # If already stored on record, return parsed questions
        if app_record.screening_questions:
            return [ScreeningQuestion(**q) for q in app_record.screening_questions]

        # Inspect live page
        job = db.query(Job).filter(Job.id == app_record.job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated job record not found."
            )

        page, context, nav_result, own_context = await browser_service.open_page(job.url)
        try:
            report = await browser_service.inspect_page_structure(page)
            questions = question_extractor.extract_questions(report)
            app_record.screening_questions = [q.model_dump() for q in questions]
            app_record.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(app_record)
            return questions
        finally:
            if own_context:
                await page.close()
                await context.close()

    def answer_screening_questions(
        self,
        db: Session,
        app_id: int,
        questions: Optional[List[ScreeningQuestion]] = None,
        profile: Optional[CandidateProfile] = None
    ) -> List[QuestionAnswer]:
        """
        Phase 33: Produce grounded, structured answers for screening questions.
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        job = db.query(Job).filter(Job.id == app_record.job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated job not found."
            )

        if profile is None:
            profile = resume_service.get_current_profile() or CandidateProfile()

        # Target questions
        if not questions:
            if app_record.screening_questions:
                target_questions = [ScreeningQuestion(**q) for q in app_record.screening_questions]
            else:
                target_questions = []
        else:
            target_questions = questions

        answers = grounded_question_agent.answer_all_questions(
            questions=target_questions,
            profile=profile,
            job=job
        )

        current_answers = dict(app_record.answers or {})
        for ans in answers:
            current_answers[ans.question_id] = ans.model_dump()

        app_record.answers = current_answers
        app_record.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(app_record)
        return answers

    def generate_tailored_resume(
        self,
        db: Session,
        app_id: int,
        profile: Optional[CandidateProfile] = None
    ) -> TailoredResume:
        """
        Phase 34: Generate job-specific tailored resume draft with factual integrity verification.
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        job = db.query(Job).filter(Job.id == app_record.job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated job not found."
            )

        if profile is None:
            profile = resume_service.get_current_profile() or CandidateProfile()

        tailored = resume_tailor.tailor_resume(profile, job)

        app_record.tailored_resume = tailored.model_dump()
        app_record.resume_version = tailored.version_id
        app_record.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(app_record)
        return tailored

    def generate_cover_letter(
        self,
        db: Session,
        app_id: int,
        custom_tone: str = "professional",
        profile: Optional[CandidateProfile] = None
    ) -> CoverLetterDraft:
        """
        Phase 35: Generate grounded, role-specific cover letter.
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        job = db.query(Job).filter(Job.id == app_record.job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated job not found."
            )

        if profile is None:
            profile = resume_service.get_current_profile() or CandidateProfile()

        draft = cover_letter_generator.generate(profile, job, custom_tone)

        app_record.cover_letter = draft.full_text
        app_record.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(app_record)
        return draft

    def update_application_content(
        self,
        db: Session,
        app_id: int,
        update_data: ApplicationContentUpdate
    ) -> Application:
        """
        Phase 35: Update editable application content (cover letter, answers, tailored resume).
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        if update_data.filled_fields is not None:
            current_fields = dict(app_record.filled_fields or {})
            current_fields.update(update_data.filled_fields)
            app_record.filled_fields = current_fields
        if update_data.cover_letter is not None:
            app_record.cover_letter = update_data.cover_letter
        if update_data.answers is not None:
            current_answers = dict(app_record.answers or {})
            current_answers.update(update_data.answers)
            app_record.answers = current_answers
        if update_data.tailored_resume is not None:
            app_record.tailored_resume = update_data.tailored_resume
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if update_data.notes is not None:
            app_record.notes = update_data.notes
        if update_data.interview_details is not None:
            app_record.interview_details = update_data.interview_details

        if update_data.status is not None:
            new_st = update_data.status.upper().strip()
            if new_st not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status '{new_st}'. Allowed: {', '.join(VALID_STATUSES)}"
                )
            if new_st != app_record.status:
                history = list(app_record.status_history or [])
                history.append({
                    "from_status": app_record.status,
                    "to_status": new_st,
                    "timestamp": now_iso,
                    "actor": "user",
                    "note": update_data.notes or "Updated status via application edit"
                })
                app_record.status_history = history
                app_record.status = new_st

        app_record.updated_at = now
        db.commit()
        db.refresh(app_record)
        return app_record

    def approve_application(self, db: Session, app_id: int, note: Optional[str] = None) -> Application:
        """
        Phase 37: Explicit Human-in-the-Loop Approval Action.
        Transitions application from READY to APPROVED and logs timestamp.
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        now = datetime.now(timezone.utc)
        history = list(app_record.status_history or [])
        history.append({
            "from_status": app_record.status,
            "to_status": "APPROVED",
            "timestamp": now.isoformat(),
            "actor": "user",
            "note": note or "Explicitly approved by user for submission"
        })

        app_record.status = "APPROVED"
        app_record.status_history = history
        app_record.approved_at = now
        app_record.updated_at = now
        db.commit()
        db.refresh(app_record)
        return app_record

    def update_application_status(
        self,
        db: Session,
        app_id: int,
        new_status: str,
        note: Optional[str] = None,
        actor: str = "user",
        interview_details: Optional[Dict[str, Any]] = None
    ) -> Application:
        """
        Phase 40: Transition application through full recruitment lifecycle.
        Statuses: SAVED, MATCHED, READY, APPROVED, SUBMITTED, INTERVIEW, OFFER, REJECTED, WITHDRAWN, FAILED.
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        new_status_norm = new_status.upper().strip()
        if new_status_norm not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{new_status}'. Allowed statuses: {', '.join(VALID_STATUSES)}"
            )

        now = datetime.now(timezone.utc)
        history = list(app_record.status_history or [])
        history.append({
            "from_status": app_record.status,
            "to_status": new_status_norm,
            "timestamp": now.isoformat(),
            "actor": actor,
            "note": note,
            "interview_details": interview_details
        })

        app_record.status = new_status_norm
        app_record.status_history = history
        if interview_details is not None:
            app_record.interview_details = interview_details
        if note:
            app_record.notes = note
        app_record.updated_at = now

        db.commit()
        db.refresh(app_record)
        return app_record

    async def submit_application(
        self,
        db: Session,
        app_id: int,
        resume_file_path: Optional[str] = None
    ) -> SubmissionResult:
        """
        Phase 38: Final submission step through browser automation.
        Phase 39: Failure recovery and loop prevention.
        MANDATORY SAFETY INVARIANT: Only APPROVED applications can be submitted.
        """
        app_record = self.get_application(db, app_id)
        if not app_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application with ID {app_id} not found."
            )

        if app_record.status != "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Application #{app_id} cannot be submitted. "
                    f"Current status is '{app_record.status}'. "
                    f"Application must be explicitly APPROVED by user before submission."
                )
            )

        job = db.query(Job).filter(Job.id == app_record.job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated job record not found."
            )

        profile = resume_service.get_current_profile() or CandidateProfile()

        result: SubmissionResult = await submission_agent.submit_application(
            application=app_record,
            job=job,
            profile=profile,
            resume_file_path=resume_file_path
        )

        now = datetime.now(timezone.utc)
        history = list(app_record.status_history or [])
        history.append({
            "from_status": "APPROVED",
            "to_status": result.status,
            "timestamp": now.isoformat(),
            "actor": "submission_agent",
            "note": result.confirmation_message if result.success else f"Submission failed: {result.failure_reason}"
        })
        app_record.status_history = history
        app_record.status = result.status

        # Update database with submission outcome
        if result.success:
            app_record.applied_at = result.applied_at or now
            app_record.confirmation_details = {
                "message": result.confirmation_message,
                "url": result.confirmation_url,
                "screenshot": result.screenshot_path
            }
            app_record.submission_screenshot = result.screenshot_path
            app_record.failure_reason = None
        else:
            app_record.failure_reason = result.failure_reason
            app_record.submission_screenshot = result.screenshot_path

        app_record.updated_at = now
        db.commit()
        db.refresh(app_record)
        return result


application_service = ApplicationService()
