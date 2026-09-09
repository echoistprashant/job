import asyncio
import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.db.database import SessionLocal, init_db
from backend.app.models.application import Application
from backend.app.models.job import Job, JobCreate
from backend.app.models.resume import CandidateProfile, CandidateDetails
from backend.app.browser.models import FormFieldDiagnostic
from backend.app.browser.field_mapper import FieldMapper
from backend.app.agents.application_agent import ApplicationAgent
from backend.app.services.job_service import job_service
from backend.app.services.resume_service import resume_service

client = TestClient(app)

APPLICATION_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Senior AI Engineer - Quick Apply</title></head>
<body>
  <h1>Apply for Senior AI Engineer</h1>
  <form id="job-app-form">
    <label for="first_name">First Name</label>
    <input type="text" id="first_name" name="first_name" required />

    <label for="last_name">Last Name</label>
    <input type="text" id="last_name" name="last_name" required />

    <label for="email">Email</label>
    <input type="email" id="email" name="email" required />

    <label for="phone">Phone Number</label>
    <input type="tel" id="phone" name="phone" />

    <label for="experience">Years of Experience</label>
    <select id="experience" name="experience">
      <option value="">Select an option</option>
      <option value="0-2">0-2 years</option>
      <option value="3-5">3-5 years</option>
    </select>

    <label for="sponsorship">Will you now or in the future require visa sponsorship?</label>
    <select id="sponsorship" name="sponsorship">
      <option value="">Choose</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </select>

    <label for="resume">Upload Resume</label>
    <input type="file" id="resume" name="resume" accept=".pdf,.docx" required />

    <button type="submit" id="submit-btn">Submit Application</button>
  </form>
</body>
</html>
"""


@pytest.fixture(autouse=True)
def clean_database():
    init_db()
    db: Session = SessionLocal()
    try:
        db.query(Application).delete()
        db.query(Job).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def test_profile() -> CandidateProfile:
    return CandidateProfile(
        candidate=CandidateDetails(
            name="Prashant Yadav",
            email="prashant.yadav@example.com",
            phone="+91-9876543210",
            linkedin="https://linkedin.com/in/prashantyadav",
            github="https://github.com/echoistprashant"
        ),
        target_roles=["AI Engineer"],
        experience_level="Entry Level",
        locations=["Remote", "Bangalore"],
        skills=["Python", "FastAPI", "Playwright"],
        minimum_match_score=75
    )


def test_field_mapper_detection():
    """Phase 27: Detect common form fields semantically without screen coordinates."""
    mapper = FieldMapper()

    f1 = FormFieldDiagnostic(tag="input", field_type="text", name="first_name", selector="input[name='first_name']")
    f2 = FormFieldDiagnostic(tag="input", field_type="email", name="user_email", selector="input[name='user_email']")
    f3 = FormFieldDiagnostic(tag="input", field_type="tel", id="cell_phone", label="Mobile Phone", selector="#cell_phone")
    f4 = FormFieldDiagnostic(tag="input", field_type="file", name="resume_doc", selector="input[type='file']")

    assert mapper.identify_field_type(f1) == "first_name"
    assert mapper.identify_field_type(f2) == "email"
    assert mapper.identify_field_type(f3) == "phone"
    assert mapper.identify_field_type(f4) == "resume"


def test_connect_fields_to_candidate_data(test_profile):
    """Phase 28: Connect detected fields to candidate data."""
    mapper = FieldMapper()

    assert mapper.get_candidate_value("first_name", test_profile) == "Prashant"
    assert mapper.get_candidate_value("last_name", test_profile) == "Yadav"
    assert mapper.get_candidate_value("email", test_profile) == "prashant.yadav@example.com"
    assert mapper.get_candidate_value("phone", test_profile) == "+91-9876543210"


def test_selects_and_ambiguous_choices(test_profile):
    """Phase 30: Resolve clear selects, flag ambiguous choices for review."""
    mapper = FieldMapper()

    # Clear experience match
    exp_field = FormFieldDiagnostic(
        tag="select",
        name="experience",
        options=["0-2 years", "3-5 years", "5+ years"],
        selector="#experience"
    )
    opt, is_ambiguous = mapper.resolve_select_option(exp_field, test_profile)
    assert opt == "0-2 years"
    assert is_ambiguous is False

    # Ambiguous sponsorship question -> flag for human review
    sponsor_field = FormFieldDiagnostic(
        tag="select",
        name="sponsorship",
        options=["Yes", "No"],
        selector="#sponsorship"
    )
    opt_sp, is_sp_ambiguous = mapper.resolve_select_option(sponsor_field, test_profile)
    assert opt_sp is None
    assert is_sp_ambiguous is True


def test_application_draft_preparation(test_profile):
    """Phase 29 & 31: Fill fields, attach resume, and stop before submission."""
    async def run():
        # Create a temporary dummy resume file for attachment testing
        temp_resume = Path("test_sessions") / "test_resume.pdf"
        temp_resume.parent.mkdir(parents=True, exist_ok=True)
        temp_resume.write_bytes(b"%PDF-1.4 dummy test pdf bytes for upload")

        agent = ApplicationAgent()
        job = Job(
            id=101,
            title="Senior AI Engineer",
            company="TechCorp",
            url=f"data:text/html,{APPLICATION_FORM_HTML}",
            source="greenhouse"
        )

        draft = await agent.prepare_application_draft(
            job=job,
            profile=test_profile,
            resume_file_path=str(temp_resume)
        )

        assert draft.status == "READY"
        assert draft.stopped_before_submission is True
        assert draft.resume_attached is True
        assert draft.filled_fields["first_name"] == "Prashant"
        assert draft.filled_fields["last_name"] == "Yadav"
        assert draft.filled_fields["email"] == "prashant.yadav@example.com"
        assert "resume_file" in draft.filled_fields
        # Ambiguous sponsorship must be in unfilled list
        assert any("sponsorship" in u for u in draft.unfilled_fields)

        temp_resume.unlink(missing_ok=True)

    asyncio.run(run())


def test_api_application_draft_endpoints(test_profile):
    """Test POST /applications/{job_id}/prepare and GET /applications API routes."""
    resume_service.save_profile(test_profile)

    db: Session = SessionLocal()
    try:
        # Create a mock job with test form
        job = Job(
            title="Senior AI Engineer",
            company="TestCorp",
            url=f"data:text/html,{APPLICATION_FORM_HTML}",
            source="greenhouse",
            description="Leading AI solutions.",
            location="Remote",
            remote=True
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    # 1. POST /applications/{job_id}/prepare
    prep_resp = client.post(f"/applications/{job_id}/prepare")
    assert prep_resp.status_code == 200
    prep_data = prep_resp.json()
    assert prep_data["job_id"] == job_id
    assert prep_data["status"] == "READY"
    assert prep_data["filled_fields"]["first_name"] == "Prashant"
    assert "email" in prep_data["filled_fields"]

    app_id = prep_data["id"]

    # 2. GET /applications
    list_resp = client.get("/applications")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(a["id"] == app_id for a in list_data["items"])

    # 3. GET /applications/{id}
    single_resp = client.get(f"/applications/{app_id}")
    assert single_resp.status_code == 200
    assert single_resp.json()["id"] == app_id
