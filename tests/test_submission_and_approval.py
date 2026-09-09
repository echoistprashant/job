import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.agents.submission_agent import submission_agent
from backend.app.db.database import SessionLocal
from backend.app.main import app
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.resume import (
    CandidateDetails,
    CandidateProfile,
    EducationItem,
    ExperienceItem,
    ProjectItem,
)
from backend.app.services.application_service import application_service
from backend.app.services.resume_service import resume_service

client = TestClient(app)

SUCCESS_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Job Application</title></head>
<body>
  <h1>Apply for Senior Engineer</h1>
  <form id="app-form" onsubmit="event.preventDefault(); document.getElementById('result').style.display='block'; document.getElementById('app-form').style.display='none';">
    <label for="first_name">First Name</label>
    <input type="text" id="first_name" name="first_name" value="" required />

    <label for="email">Email</label>
    <input type="email" id="email" name="email" value="" required />

    <button type="submit" id="submit-btn">Submit Application</button>
  </form>
  <div id="result" style="display:none;">
    <h2>Thank you for your application!</h2>
    <p>We have received your application successfully.</p>
  </div>
</body>
</html>
"""

VALIDATION_ERROR_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Job Application with Error</title></head>
<body>
  <h1>Apply for Job</h1>
  <form id="app-form" onsubmit="event.preventDefault(); document.getElementById('err-msg').style.display='block';">
    <label for="first_name">First Name</label>
    <input type="text" id="first_name" name="first_name" value="" required />

    <div class="error" id="err-msg" style="display:none; color: red;">
      Phone number format is invalid. Required format: +1-XXX-XXX-XXXX
    </div>

    <button type="submit" id="submit-btn">Submit Application</button>
  </form>
</body>
</html>
"""

CAPTCHA_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Job Application with CAPTCHA</title></head>
<body>
  <h1>Apply for Job</h1>
  <form id="app-form">
    <div class="g-recaptcha" data-sitekey="test">CAPTCHA Challenge</div>
    <iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>
    <button type="submit" id="submit-btn">Submit Application</button>
  </form>
</body>
</html>
"""


@pytest.fixture
def test_profile() -> CandidateProfile:
    return CandidateProfile(
        candidate=CandidateDetails(
            name="Prashant Yadav",
            email="prashant.yadav@example.com",
            phone="+91-9876543210",
            location="Bangalore",
            summary="Senior AI Engineer",
            education=[
                EducationItem(institution="IIT", degree="B.Tech", end_date="2021")
            ],
            experience=[
                ExperienceItem(
                    company="NextGen",
                    role="Senior Engineer",
                    start_date="2022-01",
                    end_date="Present",
                    description="AI backend",
                    current=True
                )
            ],
            projects=[
                ProjectItem(
                    title="Agent System",
                    description="Autonomous agent",
                    technologies=["Python", "FastAPI"]
                )
            ]
        ),
        skills=["Python", "FastAPI"],
        target_roles=["Senior AI Engineer"],
        remote_preference=True
    )


def test_approval_gate_enforcement(test_profile):
    """Phase 38: Verify unapproved applications CANNOT be submitted (Hard approval gate)."""
    resume_service.save_profile(test_profile)

    db: Session = SessionLocal()
    try:
        job = Job(
            title="AI Engineer",
            company="GateCorp",
            url=f"https://jobs.example.com/gate-{uuid.uuid4().hex[:8]}",
            source="greenhouse",
            description="AI engineer position",
            location="Remote",
            remote=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_rec = Application(
            job_id=job.id,
            status="READY",  # Not APPROVED
            application_url=job.url,
            source="greenhouse",
            filled_fields={"first_name": "Prashant"},
            unfilled_fields=[],
            answers={}
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)
        app_id = app_rec.id
    finally:
        db.close()

    # Attempt submission without approval -> MUST FAIL
    submit_resp = client.post(f"/applications/{app_id}/submit")
    assert submit_resp.status_code == 400
    assert "must be explicitly APPROVED" in submit_resp.json()["detail"]


def test_approve_application_lifecycle(test_profile):
    """Phase 37: Verify explicit user approval transitions status to APPROVED and sets approved_at."""
    resume_service.save_profile(test_profile)

    db: Session = SessionLocal()
    try:
        job = Job(
            title="AI Systems Lead",
            company="ApproveCorp",
            url=f"https://jobs.example.com/approve-{uuid.uuid4().hex[:8]}",
            source="greenhouse",
            description="Systems lead",
            location="Remote",
            remote=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_rec = Application(
            job_id=job.id,
            status="READY",
            application_url=job.url,
            source="greenhouse",
            filled_fields={"first_name": "Prashant"},
            unfilled_fields=[],
            answers={}
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)
        app_id = app_rec.id
    finally:
        db.close()

    # Explicit approval
    approve_resp = client.post(f"/applications/{app_id}/approve")
    assert approve_resp.status_code == 200
    data = approve_resp.json()
    assert data["status"] == "APPROVED"
    assert data["approved_at"] is not None


def test_edit_application_content(test_profile):
    """Phase 37: Verify human editing of filled fields, answers, and cover letter."""
    resume_service.save_profile(test_profile)

    db: Session = SessionLocal()
    try:
        job = Job(
            title="Backend Architect",
            company="EditCorp",
            url=f"https://jobs.example.com/edit-{uuid.uuid4().hex[:8]}",
            source="greenhouse",
            description="Backend architect",
            location="Remote",
            remote=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_rec = Application(
            job_id=job.id,
            status="READY",
            application_url=job.url,
            source="greenhouse",
            filled_fields={"first_name": "Prashant", "email": "wrong@example.com"},
            unfilled_fields=[],
            answers={"notice": "1 month"}
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)
        app_id = app_rec.id
    finally:
        db.close()

    # Edit fields via PATCH
    patch_resp = client.patch(
        f"/applications/{app_id}",
        json={
            "filled_fields": {"email": "corrected@example.com"},
            "answers": {"notice": "2 weeks"},
            "cover_letter": "I am excited to apply for this backend architect role."
        }
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["filled_fields"]["email"] == "corrected@example.com"
    assert updated["answers"]["notice"] == "2 weeks"
    assert "backend architect" in updated["cover_letter"]


@pytest.mark.anyio
async def test_successful_submission_flow(test_profile):
    """Phase 38: Controlled browser submission of an APPROVED application with confirmation detection."""
    resume_service.save_profile(test_profile)

    db: Session = SessionLocal()
    try:
        job = Job(
            title="Senior Engineer",
            company="SuccessCorp",
            url=f"data:text/html;charset=utf-8,{SUCCESS_FORM_HTML}<!-- {uuid.uuid4().hex[:8]} -->",
            source="greenhouse",
            description="AI engineer",
            location="Remote",
            remote=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_rec = Application(
            job_id=job.id,
            status="APPROVED",  # Explicitly approved
            application_url=job.url,
            source="greenhouse",
            filled_fields={"first_name": "Prashant", "email": "prashant@example.com"},
            unfilled_fields=[],
            answers={}
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)
        app_id = app_rec.id

        # Submit through application service
        result = await application_service.submit_application(db, app_id)

        assert result.success is True
        assert result.status == "SUBMITTED"
        assert "thank you" in result.confirmation_message.lower()
        assert result.screenshot_path is not None

        # Check DB record updated
        db.refresh(app_rec)
        assert app_rec.status == "SUBMITTED"
        assert app_rec.applied_at is not None
        assert app_rec.confirmation_details is not None
    finally:
        db.close()


@pytest.mark.anyio
async def test_failure_recovery_and_loop_prevention(test_profile):
    """Phase 39: Detect validation errors, record failure reason, halt without retrying."""
    resume_service.save_profile(test_profile)

    db: Session = SessionLocal()
    try:
        job = Job(
            title="Engineer",
            company="FailCorp",
            url=f"data:text/html;charset=utf-8,{VALIDATION_ERROR_FORM_HTML}<!-- {uuid.uuid4().hex[:8]} -->",
            source="greenhouse",
            description="Engineer role",
            location="Remote",
            remote=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_rec = Application(
            job_id=job.id,
            status="APPROVED",
            application_url=job.url,
            source="greenhouse",
            filled_fields={"first_name": "Prashant"},
            unfilled_fields=[],
            answers={}
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)
        app_id = app_rec.id

        # Submit
        result = await application_service.submit_application(db, app_id)

        # Must record failure and stop execution immediately
        assert result.success is False
        assert result.status == "FAILED"
        assert "validation error" in result.failure_reason.lower() or "phone number format is invalid" in result.failure_reason.lower()
        assert result.screenshot_path is not None

        # Check DB updated to FAILED
        db.refresh(app_rec)
        assert app_rec.status == "FAILED"
        assert app_rec.failure_reason is not None
    finally:
        db.close()


@pytest.mark.anyio
async def test_captcha_detection_safeguard(test_profile):
    """Phase 39: Detect CAPTCHA and halt safely without spamming or repeated clicks."""
    resume_service.save_profile(test_profile)

    db: Session = SessionLocal()
    try:
        job = Job(
            title="Engineer",
            company="CaptchaCorp",
            url=f"data:text/html;charset=utf-8,{CAPTCHA_FORM_HTML}<!-- {uuid.uuid4().hex[:8]} -->",
            source="greenhouse",
            description="Engineer role",
            location="Remote",
            remote=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        app_rec = Application(
            job_id=job.id,
            status="APPROVED",
            application_url=job.url,
            source="greenhouse",
            filled_fields={"first_name": "Prashant"},
            unfilled_fields=[],
            answers={}
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)
        app_id = app_rec.id

        result = await application_service.submit_application(db, app_id)

        assert result.success is False
        assert result.status == "FAILED"
        assert "captcha" in result.failure_reason.lower()
    finally:
        db.close()
