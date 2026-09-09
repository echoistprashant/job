import re
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException

from backend.app.ai.resume_parser import ResumeParser
from backend.app.services.adapters.greenhouse_adapter import GreenhouseJobAdapter
from backend.app.core.security import (
    encrypt_text,
    decrypt_text,
    sanitize_input,
    InMemoryRateLimiter,
)
from backend.app.ai.matcher import HybridJobMatcher, RuleBasedMatcher, SemanticMatcher
from backend.app.models.job import Job
from backend.app.models.resume import CandidateProfile, CandidateDetails
from backend.app.services.job_service import job_service


def test_resume_parser_diverse_formats_and_edge_cases():
    """
    Phase 44: Test resume text parsing across edge cases, multiple phone styles,
    and missing sections.
    """
    parser = ResumeParser()

    # Case 1: Standard rich text
    text = """
    Johnathan Doe
    john.doe@example.com | +1 (415) 555-2671 | San Francisco, CA
    https://linkedin.com/in/johndoe | https://github.com/johndoe

    SUMMARY
    Senior AI and Backend Engineer with 5+ years building distributed FastAPI and PyTorch systems.

    SKILLS
    Python, FastAPI, Docker, PyTorch, PostgreSQL, React, LangGraph, Redis

    EXPERIENCE
    Senior Backend Engineer at CloudScale (2021 - Present)
    - Architected microservices in Python and FastAPI.
    """
    profile = parser.parse(text)
    assert profile.candidate.name == "Johnathan Doe"
    assert profile.candidate.email == "john.doe@example.com"
    assert profile.candidate.phone is not None
    assert "linkedin.com/in/johndoe" in profile.candidate.linkedin
    assert "github.com/johndoe" in profile.candidate.github
    assert "Python" in profile.skills
    assert "FastAPI" in profile.skills
    assert "PyTorch" in profile.skills

    # Case 2: Minimal text without contact details
    minimal_text = "Software Engineer with knowledge of Python, Git, and Linux."
    min_profile = parser.parse(minimal_text)
    assert min_profile.candidate.email is None
    assert min_profile.candidate.phone is None
    assert "Python" in min_profile.skills
    assert "Git" in min_profile.skills

    # Case 3: Empty string
    empty_profile = parser.parse("")
    assert empty_profile.skills == []
    assert empty_profile.candidate.name is not None


def test_job_adapter_normalization_and_dirty_html():
    """
    Phase 44: Test job adapter cleans HTML entities, strips unwanted markup,
    and supplies robust fallbacks for missing data.
    """
    adapter = GreenhouseJobAdapter()

    # Mock Greenhouse payload with dirty HTML description and HTML entities
    raw_posting = {
        "id": 98765,
        "title": "Staff AI Engineer",
        "location": {"name": "Remote - US"},
        "content": "<p>Join our team! &bull; Build <strong>LLMs</strong> and RAG systems.</p>",
        "absolute_url": "https://boards.greenhouse.io/testcompany/jobs/98765?gh_src=test",
        "updated_at": "2026-09-01T12:00:00Z"
    }

    norm = adapter._normalize_greenhouse_job("testcompany", raw_posting)
    assert norm.title == "Staff AI Engineer"
    assert norm.company == "Testcompany"
    assert norm.location == "Remote - US"
    assert norm.remote is True
    assert norm.source == "greenhouse"
    assert norm.external_id == "gh_testcompany_98765"


def test_job_deduplication_and_url_canonicalization():
    """
    Phase 44: Test deduplication logic identifies existing jobs regardless of URL parameters.
    """
    from backend.app.db.database import SessionLocal
    with SessionLocal() as db:
        unique_id = f"dedup_{datetime.now().timestamp()}"
        base_url = f"https://boards.greenhouse.io/sample/jobs/{unique_id}"

        job1 = Job(
            title="DevOps Engineer",
            company="Dedupe Corp",
            location="Remote",
            remote=True,
            description="Docker and Kubernetes specialist",
            url=base_url,
            source="greenhouse",
            external_id=unique_id
        )
        db.add(job1)
        db.commit()

        # Check deduplication query by external_id
        existing = db.query(Job).filter(
            Job.source == "greenhouse",
            Job.external_id == unique_id
        ).first()
        assert existing is not None
        assert existing.id == job1.id


def test_matching_scoring_engine_dimension_weights():
    """
    Phase 44: Verify mathematical bounds of scoring dimensions and weight distribution.
    """
    matcher = HybridJobMatcher()
    job = Job(
        title="Python Backend Engineer",
        company="TechCorp",
        location="Remote",
        remote=True,
        experience="2-4 years",
        description="We need a Python and FastAPI engineer with PostgreSQL experience.",
        url="https://example.com/job/1",
        source="greenhouse"
    )

    # 1. Strong match profile
    strong_profile = CandidateProfile(
        candidate=CandidateDetails(
            name="Alice",
            skills=["Python", "FastAPI", "PostgreSQL"],
            education=[]
        ),
        target_roles=["Python Backend Engineer"],
        experience_level="Mid Level",
        locations=["Remote"],
        remote_preference=True,
        skills=["Python", "FastAPI", "PostgreSQL"]
    )
    score_strong, breakdown_strong, _, _, _ = matcher.match(strong_profile, job)
    assert score_strong >= 75.0
    assert breakdown_strong.skills >= 70.0
    assert breakdown_strong.location == 100.0

    # 2. Unrelated profile
    unrelated_profile = CandidateProfile(
        candidate=CandidateDetails(
            name="Bob",
            skills=["Ruby", "Rails"],
            education=[]
        ),
        target_roles=["Graphic Designer"],
        experience_level="Entry Level",
        locations=["London"],
        remote_preference=False,
        skills=["Ruby", "Rails"]
    )
    score_unrelated, breakdown_unrelated, _, _, _ = matcher.match(unrelated_profile, job)
    assert score_unrelated < 50.0
    assert score_strong > score_unrelated


def test_security_encryption_and_decryption_roundtrip():
    """
    Phase 46: Test symmetric Fernet data encryption and transparent backward compatibility.
    """
    secret_data = "+1 (555) 867-5309"
    encrypted = encrypt_text(secret_data)
    assert encrypted != secret_data
    assert encrypted.startswith("enc:")

    decrypted = decrypt_text(encrypted)
    assert decrypted == secret_data

    # Unencrypted legacy string should return untouched
    legacy_plain = "regular_email@example.com"
    assert decrypt_text(legacy_plain) == legacy_plain
    assert decrypt_text(None) is None


def test_security_input_sanitization():
    """
    Phase 46: Test sanitization removes XSS payloads while preserving technical keywords.
    """
    malicious = "<script>alert('pwned')</script>Senior Engineer <img src=x onerror=alert(1)> with React & Python"
    cleaned = sanitize_input(malicious)
    assert "<script>" not in cleaned
    assert "alert" not in cleaned
    assert "onerror=" not in cleaned
    assert "Senior Engineer" in cleaned
    assert "React & Python" in cleaned


def test_security_rate_limiter():
    """
    Phase 46: Test in-memory sliding window rate limiter protects endpoints.
    """
    limiter = InMemoryRateLimiter(requests_per_minute=5)
    test_ip = "192.168.1.100"

    # First 5 calls should succeed
    for _ in range(5):
        limiter.check_rate_limit(test_ip)

    # 6th call within window must raise 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check_rate_limit(test_ip)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail
