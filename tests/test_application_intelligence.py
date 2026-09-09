import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ai.cover_letter_generator import cover_letter_generator
from backend.app.ai.question_agent import grounded_question_agent
from backend.app.ai.question_extractor import ScreeningQuestion, question_extractor
from backend.app.ai.resume_tailor import resume_tailor
from backend.app.browser.models import FormDiagnosticReport, FormFieldDiagnostic
from backend.app.db.database import SessionLocal
from backend.app.main import app
from backend.app.models.application import Application, ApplicationContentUpdate
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


@pytest.fixture
def sample_profile() -> CandidateProfile:
    return CandidateProfile(
        candidate=CandidateDetails(
            name="Prashant Yadav",
            email="prashant.yadav@example.com",
            phone="+91-9876543210",
            location="Bangalore, India",
            summary="Full-stack AI systems engineer with deep expertise in Python, FastAPI, and autonomous browser agents.",
            education=[
                EducationItem(
                    institution="Indian Institute of Technology",
                    degree="B.Tech in Computer Science",
                    end_date="2021"
                )
            ],
            experience=[
                ExperienceItem(
                    company="NextGen Systems",
                    role="Senior Software Engineer",
                    start_date="2022-01",
                    end_date="Present",
                    description="Architected scalable microservices using Python and FastAPI, handling 10M daily requests.",
                    current=True
                )
            ],
            projects=[
                ProjectItem(
                    title="Autonomous Web Agent",
                    description="Built an autonomous web agent using Playwright and Python with zero human intervention required.",
                    technologies=["Python", "Playwright", "FastAPI"]
                )
            ]
        ),
        target_roles=["Senior AI Engineer", "Full Stack Engineer"],
        skills=["Python", "FastAPI", "Playwright", "SQLAlchemy", "PostgreSQL", "Docker"],
        preferred_locations=["Remote", "Bangalore"],
        remote_preference=True,
        minimum_match_score=75,
        auto_apply=False
    )


@pytest.fixture
def sample_job() -> Job:
    return Job(
        id=1,
        title="Senior AI Engineer",
        company="Cognitive Corp",
        url="https://jobs.example.com/cognitive/ai-engineer",
        source="greenhouse",
        description="We are seeking a Senior AI Engineer skilled in Python, FastAPI, and Playwright to lead web agent development.",
        location="Remote",
        remote=True
    )


def test_question_extractor_separation():
    """Phase 32: Verify question extraction separates standard profile fields from screening questions."""
    report = FormDiagnosticReport(
        url="https://jobs.example.com/apply",
        page_title="Apply for Senior AI Engineer",
        total_fields=8,
        inputs=[
            FormFieldDiagnostic(
                tag="input",
                field_type="text",
                name="first_name",
                id="first_name",
                label="First Name *",
                required=True,
                selector="#first_name"
            ),
            FormFieldDiagnostic(
                tag="input",
                field_type="email",
                name="email",
                id="email",
                label="Email *",
                required=True,
                selector="#email"
            ),
            FormFieldDiagnostic(
                tag="input",
                field_type="text",
                name="years_python",
                id="years_python",
                label="How many years of Python experience do you have?",
                required=True,
                selector="#years_python"
            )
        ],
        selects=[
            FormFieldDiagnostic(
                tag="select",
                field_type="select",
                name="work_auth",
                id="work_auth",
                label="Are you legally authorized to work in the country of this role?",
                required=True,
                options=["Yes", "No"],
                selector="#work_auth"
            )
        ],
        textareas=[
            FormFieldDiagnostic(
                tag="textarea",
                field_type="textarea",
                name="why_join",
                id="why_join",
                label="Why do you want to join Cognitive Corp?",
                required=True,
                selector="#why_join"
            ),
            FormFieldDiagnostic(
                tag="textarea",
                field_type="textarea",
                name="golang_exp",
                id="golang_exp",
                label="Describe your production experience with Golang microservices (optional)",
                required=False,
                selector="#golang_exp"
            )
        ],
        file_inputs=[
            FormFieldDiagnostic(
                tag="input",
                field_type="file",
                name="resume",
                id="resume",
                label="Upload Resume",
                required=True,
                selector="#resume"
            )
        ],
        buttons=["Submit Application"]
    )

    extracted = question_extractor.extract_questions(report)

    # Standard fields (first_name, email, resume file) must NOT be in extracted questions
    extracted_ids = [q.id for q in extracted]
    assert "first_name" not in extracted_ids
    assert "email" not in extracted_ids
    assert "resume" not in extracted_ids

    # Questions must be properly identified and categorized
    assert "years_python" in extracted_ids
    assert "work_auth" in extracted_ids
    assert "why_join" in extracted_ids
    assert "golang_exp" in extracted_ids

    why_q = next(q for q in extracted if q.id == "why_join")
    assert why_q.category == "motivation"
    assert why_q.required is True

    golang_q = next(q for q in extracted if q.id == "golang_exp")
    assert golang_q.category == "experience"
    assert golang_q.required is False


def test_grounded_question_agent_factual(sample_profile, sample_job):
    """Phase 33: Verify grounded question agent produces factual answers for supported questions."""
    # 1. Supported technical question
    q_python = ScreeningQuestion(
        id="q_py",
        prompt="Describe your experience with FastAPI and web automation",
        field_type="textarea",
        required=True,
        selector="#q_py",
        category="experience"
    )
    ans_py = grounded_question_agent.answer_question(q_python, sample_profile, sample_job)
    assert ans_py.needs_review is False
    assert ans_py.confidence >= 0.85
    assert len(ans_py.grounded_facts) > 0
    assert "FastAPI" in ans_py.answer or "Playwright" in ans_py.answer

    # 2. Motivation question
    q_why = ScreeningQuestion(
        id="q_why",
        prompt="Why do you want to work at Cognitive Corp?",
        field_type="textarea",
        required=True,
        selector="#q_why",
        category="motivation"
    )
    ans_why = grounded_question_agent.answer_question(q_why, sample_profile, sample_job)
    assert ans_why.needs_review is False
    assert "Cognitive Corp" in ans_why.answer
    assert "Senior AI Engineer" in ans_why.answer


def test_grounded_question_agent_zero_hallucination(sample_profile, sample_job):
    """Phase 33: STRICT ZERO-HALLUCINATION SAFEGUARD. Forbid invented credentials."""
    # Question asks about Golang which is NOT in candidate profile
    q_unsupported = ScreeningQuestion(
        id="q_go",
        prompt="Describe your 5+ years of production experience with Golang",
        field_type="textarea",
        required=True,
        selector="#q_go",
        category="experience"
    )
    ans_go = grounded_question_agent.answer_question(q_unsupported, sample_profile, sample_job)

    # Must flag for human review and state absence of extensive production experience
    assert ans_go.needs_review is True
    assert ans_go.confidence <= 0.6
    assert "Golang" in ans_go.review_reason
    assert "do not have extensive production experience with Golang" in ans_go.answer


def test_resume_tailoring_and_factual_integrity(sample_profile, sample_job):
    """Phase 34: Resume tailoring highlights relevant skills while verifying 100% factual integrity."""
    tailored = resume_tailor.tailor_resume(sample_profile, sample_job)

    # Must prioritize matching skills
    assert "Python" in tailored.highlighted_skills
    assert "FastAPI" in tailored.highlighted_skills
    assert "Playwright" in tailored.highlighted_skills

    # Must verify factual integrity
    assert tailored.factual_integrity_verified is True

    # Check that companies and education were not fabricated or altered
    tailored_companies = {e["company"] for e in tailored.reordered_experiences}
    assert tailored_companies == {"NextGen Systems"}

    tailored_institutions = {e["institution"] for e in tailored.education}
    assert tailored_institutions == {"Indian Institute of Technology"}

    # Projects must be re-ranked by relevance
    assert len(tailored.reordered_projects) > 0
    assert tailored.reordered_projects[0]["name"] == "Autonomous Web Agent"


def test_cover_letter_generation(sample_profile, sample_job):
    """Phase 35: Cover letter generation produces a role-specific, grounded draft."""
    draft = cover_letter_generator.generate(sample_profile, sample_job, custom_tone="enthusiastic")

    assert draft.job_id == sample_job.id
    assert "Cognitive Corp" in draft.company
    assert "Senior AI Engineer" in draft.role
    assert "Cognitive Corp" in draft.full_text
    assert "Dear Cognitive Corp Hiring Team," in draft.full_text
    assert "Prashant Yadav" in draft.closing
    assert "Autonomous Web Agent" in draft.full_text


def test_api_application_intelligence_endpoints(sample_profile):
    """Test REST API routes for questions, tailoring, cover letter, and editing."""
    resume_service.save_profile(sample_profile)

    import uuid
    unique_suffix = uuid.uuid4().hex[:8]

    db: Session = SessionLocal()
    try:
        job = Job(
            title="Senior AI Engineer",
            company="Cognitive Corp",
            url=f"https://jobs.example.com/cognitive/ai-engineer-{unique_suffix}",
            source="greenhouse",
            description="Developing AI systems using Python, FastAPI, and Playwright.",
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
            filled_fields={"first_name": "Prashant", "email": "prashant@example.com"},
            unfilled_fields=[],
            screening_questions=[
                {
                    "id": "why_us",
                    "prompt": "Why do you want to join Cognitive Corp?",
                    "field_type": "textarea",
                    "required": True,
                    "options": [],
                    "selector": "#why_us",
                    "category": "motivation"
                }
            ],
            answers={}
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)
        app_id = app_rec.id
    finally:
        db.close()

    # 1. POST /applications/{app_id}/answer-questions
    ans_resp = client.post(f"/applications/{app_id}/answer-questions")
    assert ans_resp.status_code == 200
    answers = ans_resp.json()
    assert len(answers) == 1
    assert answers[0]["question_id"] == "why_us"
    assert "Cognitive Corp" in answers[0]["answer"]

    # 2. POST /applications/{app_id}/tailor-resume
    tailor_resp = client.post(f"/applications/{app_id}/tailor-resume")
    assert tailor_resp.status_code == 200
    tailor_data = tailor_resp.json()
    assert tailor_data["factual_integrity_verified"] is True
    assert "Python" in tailor_data["highlighted_skills"]

    # 3. POST /applications/{app_id}/cover-letter
    cl_resp = client.post(f"/applications/{app_id}/cover-letter", json={"tone": "professional"})
    assert cl_resp.status_code == 200
    cl_data = cl_resp.json()
    assert "Cognitive Corp" in cl_data["full_text"]

    # 4. PATCH /applications/{app_id} (Human Editing)
    custom_letter = "Custom edited cover letter by Prashant."
    patch_resp = client.patch(
        f"/applications/{app_id}",
        json={"cover_letter": custom_letter, "status": "APPROVED"}
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["cover_letter"] == custom_letter
    assert updated["status"] == "APPROVED"
