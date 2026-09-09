from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.agents.application_agent import application_agent
from backend.app.models.application import Application, ApplicationDraftResult
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
        app_record = db.query(Application).filter(Application.job_id == job_id).first()
        if app_record:
            app_record.status = draft_result.status
            app_record.filled_fields = draft_result.filled_fields
            app_record.unfilled_fields = draft_result.unfilled_fields
            app_record.application_url = job.url
            app_record.source = job.source
            app_record.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(app_record)
            return app_record

        # Create new application record
        new_app = Application(
            job_id=job_id,
            status=draft_result.status,
            application_url=job.url,
            source=job.source,
            filled_fields=draft_result.filled_fields,
            unfilled_fields=draft_result.unfilled_fields,
            answers={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
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


application_service = ApplicationService()
