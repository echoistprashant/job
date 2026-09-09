from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.app.db.database import get_db
from backend.app.models.job import JobFilterParams, JobListResponse, JobResponse
from backend.app.models.match import JobMatchResponse
from backend.app.services.job_service import job_service

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobSearchRequest(BaseModel):
    keywords: Optional[List[str]] = Field(default=None, json_schema_extra={"example": ["AI Engineer", "Python"]})
    locations: Optional[List[str]] = Field(default=None, json_schema_extra={"example": ["Remote", "India"]})
    limit_per_source: int = Field(default=20, ge=1, le=100)


class JobSearchResponse(BaseModel):
    status: str
    new_jobs_added: int
    total_jobs_scanned: int
    message: str


@router.post("/search", response_model=JobSearchResponse, status_code=status.HTTP_200_OK)
async def search_and_collect_jobs(
    request: JobSearchRequest,
    db: Session = Depends(get_db)
):
    """Run job adapters to collect, normalize, deduplicate, and persist jobs."""
    new_added, total_scanned = await job_service.collect_and_store_jobs(
        db=db,
        keywords=request.keywords,
        locations=request.locations,
        limit_per_source=request.limit_per_source
    )
    return JobSearchResponse(
        status="success",
        new_jobs_added=new_added,
        total_jobs_scanned=total_scanned,
        message=f"Scanned {total_scanned} jobs across adapters; added {new_added} new unique jobs."
    )


@router.get("", response_model=JobListResponse, status_code=status.HTTP_200_OK)
def list_jobs(
    keyword: Optional[str] = Query(None, description="Search term in title, company, or description"),
    location: Optional[str] = Query(None, description="Filter by location"),
    remote_only: Optional[bool] = Query(None, description="Only show remote positions"),
    experience: Optional[str] = Query(None, description="Filter by experience level"),
    source: Optional[str] = Query(None, description="Filter by source board"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve normalized and deduplicated jobs with filtering and pagination."""
    params = JobFilterParams(
        keyword=keyword,
        location=location,
        remote_only=remote_only,
        experience=experience,
        source=source,
        limit=limit,
        offset=offset
    )
    jobs, total = job_service.get_jobs(db, params)
    return JobListResponse(
        total=total,
        items=[JobResponse.model_validate(j) for j in jobs]
    )


@router.get("/{job_id}", response_model=JobResponse, status_code=status.HTTP_200_OK)
def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve details for a single job by its ID."""
    job = job_service.get_job_by_id(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )
    return JobResponse.model_validate(job)


@router.post("/{job_id}/match", response_model=JobMatchResponse, status_code=status.HTTP_200_OK)
def match_job_with_candidate_profile(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Compute and persist 6-dimension AI match score for a job against the candidate profile."""
    from backend.app.models.match import format_job_match
    match = job_service.match_job(db=db, job_id=job_id)
    return format_job_match(match)


@router.get("/{job_id}/match", response_model=JobMatchResponse, status_code=status.HTTP_200_OK)
def get_job_match_result(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve existing match score and breakdown for a job."""
    from backend.app.models.match import format_job_match
    match = job_service.get_job_match(db=db, job_id=job_id)
    if not match:
        # If not matched yet, compute on demand
        match = job_service.match_job(db=db, job_id=job_id)
    return format_job_match(match)

