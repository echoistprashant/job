from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from backend.app.models.job import Job, JobCreate, JobFilterParams
from backend.app.services.adapters.base import BaseJobAdapter
from backend.app.services.adapters.greenhouse_adapter import GreenhouseJobAdapter


class JobService:
    def __init__(self, adapters: Optional[List[BaseJobAdapter]] = None):
        self._adapters: List[BaseJobAdapter] = adapters or [GreenhouseJobAdapter()]

    def store_job(self, db: Session, job_in: JobCreate) -> Tuple[Job, bool]:
        """
        Store a normalized job with strict deduplication.
        Returns (job_instance, was_created).
        """
        # Deduplication Rule 1: Check by source + external_id if external_id is present
        existing_job = None
        if job_in.external_id:
            existing_job = (
                db.query(Job)
                .filter(and_(Job.source == job_in.source, Job.external_id == job_in.external_id))
                .first()
            )

        # Deduplication Rule 2: Check by canonical URL
        if not existing_job:
            existing_job = db.query(Job).filter(Job.url == job_in.url).first()

        if existing_job:
            # Job already exists -> update fields & timestamp without creating duplicate
            existing_job.title = job_in.title
            existing_job.company = job_in.company
            existing_job.location = job_in.location
            existing_job.remote = job_in.remote
            existing_job.experience = job_in.experience
            existing_job.description = job_in.description
            existing_job.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_job)
            return existing_job, False

        # Otherwise create new record
        new_job = Job(
            title=job_in.title,
            company=job_in.company,
            location=job_in.location,
            remote=job_in.remote,
            experience=job_in.experience,
            description=job_in.description,
            url=job_in.url,
            source=job_in.source,
            external_id=job_in.external_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        return new_job, True

    async def collect_and_store_jobs(
        self,
        db: Session,
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        limit_per_source: int = 50
    ) -> Tuple[int, int]:
        """
        Collect jobs from all registered adapters, normalize, deduplicate, and store.
        Returns (new_jobs_count, total_collected_count).
        """
        new_count = 0
        total_collected = 0

        for adapter in self._adapters:
            normalized_jobs = await adapter.fetch_jobs(
                keywords=keywords,
                locations=locations,
                limit=limit_per_source
            )
            total_collected += len(normalized_jobs)
            for job_in in normalized_jobs:
                _, created = self.store_job(db, job_in)
                if created:
                    new_count += 1

        return new_count, total_collected

    def get_jobs(
        self,
        db: Session,
        params: JobFilterParams
    ) -> Tuple[List[Job], int]:
        """Query jobs with multi-attribute filtering and pagination."""
        query = db.query(Job)

        # Keyword filter (title or description)
        if params.keyword:
            kw = f"%{params.keyword.lower()}%"
            query = query.filter(
                or_(
                    Job.title.ilike(kw),
                    Job.description.ilike(kw),
                    Job.company.ilike(kw)
                )
            )

        # Location filter
        if params.location:
            loc = f"%{params.location.lower()}%"
            query = query.filter(Job.location.ilike(loc))

        # Remote only filter
        if params.remote_only is not None:
            query = query.filter(Job.remote == params.remote_only)

        # Source filter
        if params.source:
            query = query.filter(Job.source == params.source)

        # Experience filter
        if params.experience:
            exp = f"%{params.experience.lower()}%"
            query = query.filter(Job.experience.ilike(exp))

        total = query.count()
        jobs = query.order_by(Job.created_at.desc()).offset(params.offset).limit(params.limit).all()
        return jobs, total

    def get_job_by_id(self, db: Session, job_id: int) -> Optional[Job]:
        """Retrieve a specific job by its primary key ID."""
        return db.query(Job).filter(Job.id == job_id).first()


job_service = JobService()
