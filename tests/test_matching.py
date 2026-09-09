import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.db.database import SessionLocal, init_db
from backend.app.models.job import Job, JobCreate
from backend.app.models.match import JobMatch
from backend.app.models.resume import CandidateProfile, CandidateDetails
from backend.app.ai.matcher import RuleBasedMatcher, SemanticMatcher, LLMMatchReasoner, hybrid_matcher
from backend.app.services.job_service import job_service
from backend.app.services.resume_service import resume_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure clean database tables before each test."""
    init_db()
    db = SessionLocal()
    try:
        db.query(JobMatch).delete()
        db.query(Job).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def sample_ai_profile() -> CandidateProfile:
    """Fixture providing a standard AI candidate profile."""
    return CandidateProfile(
        candidate=CandidateDetails(
            name="Prashant Yadav",
            email="prashant@example.com",
            skills=["Python", "FastAPI", "LangChain", "LLM", "RAG", "Docker", "PostgreSQL", "PyTorch"]
        ),
        target_roles=["AI Engineer", "ML Engineer", "Backend Engineer"],
        experience_level="Entry Level",
        locations=["Remote", "India"],
        skills=["Python", "FastAPI", "LangChain", "LLM", "RAG", "Docker", "PostgreSQL", "PyTorch"],
        remote_preference=True,
        minimum_match_score=75,
        auto_apply=False
    )


def test_rule_based_matcher(sample_ai_profile):
    """Phase 14: Rule-based matcher calculates deterministic scores before LLM."""
    matcher = RuleBasedMatcher()

    # 1. Skills overlap
    score, matched, missing = matcher.evaluate_skills(
        sample_ai_profile.skills,
        "We are looking for an AI Engineer with Python, FastAPI, and Docker experience."
    )
    assert score > 50.0
    assert "Python" in matched
    assert "FastAPI" in matched
    assert "Docker" in matched

    # 2. Target role match
    role_score = matcher.evaluate_role(sample_ai_profile.target_roles, "Senior AI Engineer")
    assert role_score >= 80.0

    unrelated_role_score = matcher.evaluate_role(sample_ai_profile.target_roles, "Lead Accountant")
    assert unrelated_role_score <= 30.0


def test_semantic_matcher_discrimination():
    """Phase 15: Semantically similar jobs rank substantially higher than unrelated jobs."""
    semantic_matcher = SemanticMatcher()

    candidate_text = "AI Engineer Machine Learning Deep Learning PyTorch LLM RAG LangChain Python FastAPI"
    related_job = "Machine Learning Engineer to build LLM pipelines, RAG applications, and PyTorch models."
    unrelated_job = "Accountant and Bookkeeper responsible for corporate tax filing and ledger audits."

    score_related = semantic_matcher.calculate_similarity(candidate_text, related_job)
    score_unrelated = semantic_matcher.calculate_similarity(candidate_text, unrelated_job)

    assert score_related > score_unrelated
    assert score_related > 30.0
    assert score_unrelated < 10.0


def test_llm_reasoning_structure():
    """Phase 16: Structured qualitative strengths, gaps, and grounded fit summary."""
    reasoner = LLMMatchReasoner()
    dummy_job = Job(
        title="AI Engineer",
        company="TechCorp",
        location="Remote",
        remote=True,
        experience="0-2 years",
        description="Python, FastAPI, Kubernetes",
        url="https://example.com/job/1"
    )

    strengths, gaps, explanation = reasoner.generate_reasoning(
        candidate_skills=["Python", "FastAPI"],
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Kubernetes"],
        job=dummy_job,
        overall_score=88.5
    )

    assert isinstance(strengths, list)
    assert isinstance(gaps, list)
    assert isinstance(explanation, str)
    assert any("Python" in s for s in strengths)
    assert any("Kubernetes" in g for g in gaps)
    assert "88.5%" in explanation


def test_final_weighted_scoring_and_db_persistence(sample_ai_profile):
    """Phase 17: Combine rules, semantic similarity & reasoning with 6-dimension weights and save to DB."""
    resume_service.save_profile(sample_ai_profile)

    db: Session = SessionLocal()
    try:
        job = JobCreate(
            title="AI Engineer",
            company="OpenMind",
            location="Remote",
            remote=True,
            experience="0-2 years",
            description="We build agentic LLM solutions with Python, FastAPI, and RAG.",
            url="https://boards.greenhouse.io/openmind/jobs/5001",
            source="greenhouse",
            external_id="gh_openmind_5001"
        )
        saved_job, _ = job_service.store_job(db, job)

        # Match job
        job_match = job_service.match_job(db, saved_job.id, sample_ai_profile)

        assert job_match.id is not None
        assert job_match.job_id == saved_job.id
        assert 0.0 <= job_match.score <= 100.0
        assert job_match.skills_score > 0
        assert job_match.role_score > 0
        assert job_match.location_score == 100.0  # Remote match
        assert len(job_match.strengths) > 0
        assert len(job_match.explanation) > 0

        # Verify exact 6-dimension weighted calculation
        calculated_composite = (
            0.35 * job_match.skills_score +
            0.20 * job_match.experience_score +
            0.20 * job_match.role_score +
            0.10 * job_match.location_score +
            0.10 * job_match.responsibilities_score +
            0.05 * job_match.education_score
        )
        assert pytest.approx(job_match.score, 0.2) == calculated_composite
    finally:
        db.close()


def test_api_matching_endpoints(sample_ai_profile):
    """Test POST /jobs/{id}/match and GET /jobs/{id}/match endpoints."""
    resume_service.save_profile(sample_ai_profile)

    # Store a test job first via service
    db: Session = SessionLocal()
    try:
        job = JobCreate(
            title="Backend Engineer",
            company="NexusData",
            location="Bangalore, India",
            remote=True,
            experience="1-3 years",
            description="FastAPI, PostgreSQL, Redis, Python development.",
            url="https://boards.greenhouse.io/nexusdata/jobs/6001",
            source="greenhouse",
            external_id="gh_nexusdata_6001"
        )
        saved_job, _ = job_service.store_job(db, job)
        job_id = saved_job.id
    finally:
        db.close()

    # 1. POST /jobs/{id}/match
    post_resp = client.post(f"/jobs/{job_id}/match")
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["job_id"] == job_id
    assert "breakdown" in post_data
    assert post_data["breakdown"]["skills"] > 0
    assert post_data["breakdown"]["role"] > 0
    assert "strengths" in post_data
    assert "gaps" in post_data
    assert "explanation" in post_data

    # 2. GET /jobs/{id}/match
    get_resp = client.get(f"/jobs/{job_id}/match")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["id"] == post_data["id"]
    assert get_data["score"] == post_data["score"]

    # 3. Non-existent job match -> 404
    not_found = client.post("/jobs/999999/match")
    assert not_found.status_code == 404
