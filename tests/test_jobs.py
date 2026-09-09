import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.db.database import SessionLocal, init_db
from backend.app.models.job import Job, JobCreate, JobFilterParams
from backend.app.services.job_service import job_service
from backend.app.services.adapters.greenhouse_adapter import GreenhouseJobAdapter

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure clean database tables before each test."""
    init_db()
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.commit()
    finally:
        db.close()
    yield


def test_job_model_and_persistence():
    """Phase 9 & 10: Store and retrieve a Job model using SQLAlchemy."""
    db: Session = SessionLocal()
    try:
        sample_job = JobCreate(
            title="Lead AI Engineer",
            company="NeuralSystems",
            location="Bangalore, India",
            remote=True,
            experience="3-5 years",
            description="Leading development of state-of-the-art agentic pipelines.",
            url="https://boards.greenhouse.io/neuralsystems/jobs/9001",
            source="greenhouse",
            external_id="gh_neuralsystems_9001"
        )
        saved_job, created = job_service.store_job(db, sample_job)
        assert created is True
        assert saved_job.id is not None
        assert saved_job.title == "Lead AI Engineer"
        assert saved_job.created_at is not None
        assert saved_job.updated_at is not None

        # Fetch directly from DB
        fetched = db.query(Job).filter(Job.id == saved_job.id).first()
        assert fetched is not None
        assert fetched.company == "NeuralSystems"
        assert fetched.remote is True
    finally:
        db.close()


import asyncio


def test_greenhouse_adapter_normalization():
    """Phase 11: Greenhouse adapter returns normalized JobCreate objects."""
    adapter = GreenhouseJobAdapter()
    jobs = asyncio.run(adapter.fetch_jobs(keywords=["AI", "Engineer"], limit=10))
    assert len(jobs) > 0
    for j in jobs:
        assert isinstance(j, JobCreate)
        assert j.title
        assert j.company
        assert j.url
        assert j.source == "greenhouse"



def test_job_deduplication():
    """Phase 12: Avoid storing the same external job twice."""
    db: Session = SessionLocal()
    try:
        job_data = JobCreate(
            title="Senior Python Architect",
            company="ScaleUp",
            location="Remote",
            remote=True,
            experience="5+ years",
            description="Architecting microservices with FastAPI and async queues.",
            url="https://boards.greenhouse.io/scaleup/jobs/8888",
            source="greenhouse",
            external_id="gh_scaleup_8888"
        )

        # First insert -> created
        job1, created1 = job_service.store_job(db, job_data)
        assert created1 is True

        # Second insert with same external ID and URL -> updated, not created
        job2, created2 = job_service.store_job(db, job_data)
        assert created2 is False
        assert job1.id == job2.id

        # Query total count for this external ID
        count = db.query(Job).filter(Job.external_id == "gh_scaleup_8888").count()
        assert count == 1
    finally:
        db.close()


def test_job_filtering():
    """Phase 13: Filter jobs by keyword, location, and remote status."""
    db: Session = SessionLocal()
    try:
        j1 = JobCreate(
            title="Computer Vision Researcher",
            company="VisionTech",
            location="Pune, India",
            remote=False,
            experience="2-4 years",
            description="Deep learning models for object recognition.",
            url="https://example.com/jobs/cv-1",
            source="manual",
            external_id="man_cv_1"
        )
        j2 = JobCreate(
            title="Backend Golang Engineer",
            company="GopherCorp",
            location="Remote",
            remote=True,
            experience="2-4 years",
            description="High throughput distributed messaging services.",
            url="https://example.com/jobs/go-2",
            source="manual",
            external_id="man_go_2"
        )
        job_service.store_job(db, j1)
        job_service.store_job(db, j2)

        # Filter by keyword "Vision"
        res_kw, total_kw = job_service.get_jobs(db, JobFilterParams(keyword="Vision"))
        assert any(j.title == "Computer Vision Researcher" for j in res_kw)
        assert not any(j.title == "Backend Golang Engineer" for j in res_kw)

        # Filter by remote
        res_rem, total_rem = job_service.get_jobs(db, JobFilterParams(remote_only=True, keyword="Golang"))
        assert any(j.title == "Backend Golang Engineer" for j in res_rem)
    finally:
        db.close()


def test_api_jobs_search_and_list():
    """Test POST /jobs/search, GET /jobs, and GET /jobs/{id} API endpoints."""
    # 1. Search & Collect
    search_resp = client.post(
        "/jobs/search",
        json={"keywords": ["AI Engineer", "Backend"], "limit_per_source": 10}
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["status"] == "success"
    assert search_data["total_jobs_scanned"] > 0

    # 2. List Jobs
    list_resp = client.get("/jobs?limit=10")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] > 0
    assert len(list_data["items"]) > 0
    
    first_job_id = list_data["items"][0]["id"]

    # 3. Get single job
    get_resp = client.get(f"/jobs/{first_job_id}")
    assert get_resp.status_code == 200
    single_job = get_resp.json()
    assert single_job["id"] == first_job_id
    assert single_job["title"]

    # 4. Get non-existent job -> 404
    not_found_resp = client.get("/jobs/999999")
    assert not_found_resp.status_code == 404
