from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.app.db.database import get_db
from backend.app.models.job import Job, JobFilterParams, JobListResponse, JobResponse
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


class AsyncTaskSubmitResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post("/search/async", response_model=AsyncTaskSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def search_and_collect_jobs_async(
    request: JobSearchRequest,
):
    """
    Phase 42: Asynchronously run job search, collection, deduplication, and persistence
    outside the HTTP request cycle using the background task runner.
    """
    from backend.app.core.task_runner import task_runner
    from backend.app.db.database import SessionLocal

    async def _run_search():
        with SessionLocal() as db_session:
            new_added, total_scanned = await job_service.collect_and_store_jobs(
                db=db_session,
                keywords=request.keywords,
                locations=request.locations,
                limit_per_source=request.limit_per_source
            )
            return {
                "new_jobs_added": new_added,
                "total_jobs_scanned": total_scanned,
                "status": "completed"
            }

    task_id = task_runner.submit_task("job_search_and_collection", _run_search)
    return AsyncTaskSubmitResponse(
        task_id=task_id,
        status="PENDING",
        message="Job collection task submitted to background worker."
    )


@router.post("/search", response_model=JobSearchResponse, status_code=status.HTTP_200_OK)
async def search_and_collect_jobs(
    request: JobSearchRequest,
    db: Session = Depends(get_db)
):
    """Run job adapters to collect, normalize, deduplicate, and persist jobs synchronously."""
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


class JobUrlIngestRequest(BaseModel):
    url: str
    company: Optional[str] = None
    title: Optional[str] = None


@router.post("/ingest-url", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def ingest_job_from_url(
    request: JobUrlIngestRequest,
    db: Session = Depends(get_db)
):
    """
    Ingest a job posting from any URL (Greenhouse, Lever, LinkedIn, or any career page),
    parse its metadata, store it with deduplication, and compute match score.
    """
    import re
    import httpx
    from backend.app.models.job import JobCreate

    raw_url = request.url.strip()
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = f"https://{raw_url}"

    # Check if already in DB
    existing = db.query(Job).filter(Job.url == raw_url).first()
    if existing:
        return JobResponse.model_validate(existing)

    title = request.title or "Software Engineer"
    company = request.company or "Company"
    location = "Remote"
    remote = True
    description = ""
    source = "web"

    # Greenhouse URL detection: boards.greenhouse.io/{board}/jobs/{id}
    gh_match = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", raw_url)
    if gh_match:
        board_token = gh_match.group(1)
        job_id = gh_match.group(2)
        source = "greenhouse"
        try:
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?content=true"
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get(api_url)
                if r.status_code == 200:
                    d = r.json()
                    title = d.get("title", title)
                    company = board_token.capitalize()
                    loc_data = d.get("location", {})
                    location = loc_data.get("name", "Remote") if isinstance(loc_data, dict) else str(loc_data)
                    remote = "remote" in location.lower() or "remote" in title.lower()
                    description = d.get("content", "")
        except Exception:
            pass

    # Lever URL detection: jobs.lever.co/{company}/{id}
    lever_match = re.search(r"jobs\.lever\.co/([^/]+)/([a-zA-Z0-9-]+)", raw_url)
    if lever_match:
        lever_company = lever_match.group(1)
        lever_id = lever_match.group(2)
        source = "lever"
        try:
            api_url = f"https://api.lever.co/v0/postings/{lever_company}/{lever_id}"
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get(api_url)
                if r.status_code == 200:
                    d = r.json()
                    title = d.get("text", title)
                    company = lever_company.capitalize()
                    cats = d.get("categories", {})
                    location = cats.get("location", "Remote") if isinstance(cats, dict) else "Remote"
                    remote = "remote" in str(d.get("workplaceType", "")).lower() or "remote" in location.lower()
                    description = d.get("descriptionPlain") or d.get("description", "")
        except Exception:
            pass

    # Generic webpage fallback if description is still empty
    if not description:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIJobAgent/1.0"}
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
                resp = await client.get(raw_url)
                if resp.status_code == 200:
                    html_text = resp.text
                    t_match = re.search(r"<title[^>]*>([^<]+)</title>", html_text, re.IGNORECASE)
                    if t_match and not request.title:
                        title_candidate = t_match.group(1).strip()
                        parts = re.split(r"\s*[-|–—at]\s*", title_candidate)
                        if len(parts) >= 2:
                            title = parts[0].strip()
                            if not request.company:
                                company = parts[-1].strip()
                        else:
                            title = title_candidate

                    desc_match = re.search(r'<meta\s+[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
                    if not desc_match:
                        desc_match = re.search(r'<meta\s+[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
                    if desc_match:
                        description = desc_match.group(1).strip()
                    else:
                        body_match = re.search(r"<body[^>]*>([\s\S]*?)</body>", html_text, re.IGNORECASE)
                        body_text = body_match.group(1) if body_match else html_text
                        clean_text = re.sub(r"<[^>]+>", " ", body_text)
                        clean_text = re.sub(r"\s+", " ", clean_text).strip()
                        description = clean_text[:2500]
        except Exception:
            description = f"Job listing at {raw_url}"

    if not description:
        description = f"{title} position at {company}. Apply directly at {raw_url}"

    job_create = JobCreate(
        title=title,
        company=company,
        location=location or "Remote",
        remote=remote,
        experience="1-4 years",
        description=description,
        url=raw_url,
        source=source
    )
    job_record, _ = job_service.store_job(db, job_create)

    # Automatically compute match score
    try:
        job_service.match_job(db=db, job_id=job_record.id)
    except Exception:
        pass

    return JobResponse.model_validate(job_record)


