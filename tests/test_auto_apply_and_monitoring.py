import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.app.ai.auto_apply_rules import AutoApplyPolicy, auto_apply_rules
from backend.app.ai.question_extractor import ScreeningQuestion
from backend.app.ai.question_agent import QuestionAnswer
from backend.app.db.database import SessionLocal
from backend.app.main import app
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.match import JobMatch
from backend.app.models.resume import CandidateDetails, CandidateProfile, ExperienceItem
from backend.app.services.auto_apply_service import auto_apply_service
from backend.app.services.resume_service import resume_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown_profile():
    # Setup candidate profile
    profile = CandidateProfile(
        candidate=CandidateDetails(
            first_name="Jane",
            last_name="AutoTester",
            email="jane.autotester@example.com",
            phone="+1-555-0199",
            location="San Francisco, CA",
            linkedin_url="https://linkedin.com/in/janeautotester",
            github_url="https://github.com/janeautotester",
            target_roles=["Senior Python Engineer", "Backend Lead"]
        ),
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        experience=[
            ExperienceItem(
                company="Tech Corp",
                title="Python Developer",
                start_date="2020-01",
                end_date="2024-01",
                bullets=["Engineered microservices", "Automated deployment pipelines"]
            )
        ]
    )
    resume_service.save_profile(profile)
    # Reset policy to default state
    auto_apply_service.update_policy(AutoApplyPolicy())
    yield
    # Reset policy after tests
    auto_apply_service.update_policy(AutoApplyPolicy())


def test_auto_apply_policy_crud():
    # 1. Get default policy
    resp = client.get("/auto-apply/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["minimum_match_score"] == 80.0
    assert data["max_applications_per_day"] == 5

    # 2. Update policy
    updated_policy = {
        "enabled": True,
        "minimum_match_score": 85.5,
        "max_applications_per_day": 15,
        "excluded_companies": ["SpamCorp", "BadFirm"],
        "excluded_keywords": ["unpaid", "internship"],
        "remote_only": True,
        "require_all_skills_grounded": True,
        "target_roles": ["Senior Python Engineer"]
    }
    post_resp = client.post("/auto-apply/policy", json=updated_policy)
    assert post_resp.status_code == 200
    new_data = post_resp.json()
    assert new_data["enabled"] is True
    assert new_data["minimum_match_score"] == 85.5
    assert new_data["max_applications_per_day"] == 15
    assert "SpamCorp" in new_data["excluded_companies"]
    assert new_data["remote_only"] is True

    # 3. Verify get returns updated policy
    get_resp = client.get("/auto-apply/policy")
    assert get_resp.status_code == 200
    assert get_resp.json()["minimum_match_score"] == 85.5


def test_auto_apply_rules_engine_evaluations():
    with SessionLocal() as db:
        test_run_id = str(uuid.uuid4())[:8]
        profile = resume_service.get_current_profile()
        policy = AutoApplyPolicy(
            minimum_match_score=80.0,
            target_roles=["Senior Python Engineer", "DevOps Lead"],
            excluded_companies=["Toxic Inc"],
            excluded_keywords=["No Pay"],
            remote_only=True
        )

        # Case 1: Excluded company
        bad_company_job = Job(
            title=f"DevOps Lead {test_run_id}",
            company="Toxic Inc",
            location="Remote",
            remote=True,
            source="test",
            url=f"https://toxic.example.com/jobs/{test_run_id}",
            description="We build things fast."
        )
        db.add(bad_company_job)
        db.commit()

        eval_bad_co = auto_apply_rules.evaluate_job(bad_company_job, profile, policy, db)
        assert not eval_bad_co.eligible
        assert "excluded_company" in eval_bad_co.failed_rules

        # Case 2: Excluded keyword in description
        unpaid_job = Job(
            title=f"DevOps Lead {test_run_id} 2",
            company="Clean Co",
            location="Remote",
            remote=True,
            source="test",
            url=f"https://cleanco.example.com/{test_run_id}",
            description="Great opportunity with No Pay for first 3 months."
        )
        db.add(unpaid_job)
        db.commit()

        eval_unpaid = auto_apply_rules.evaluate_job(unpaid_job, profile, policy, db)
        assert not eval_unpaid.eligible
        assert "excluded_keyword" in eval_unpaid.failed_rules

        # Case 3: Non-remote when remote is required
        onsite_job = Job(
            title=f"Senior Python Engineer {test_run_id} 3",
            company="Clean Co",
            location="New York, NY",
            remote=False,
            source="test",
            url=f"https://cleanco.example.com/onsite/{test_run_id}",
            description="Must come to office 5 days a week."
        )
        db.add(onsite_job)
        db.commit()

        eval_onsite = auto_apply_rules.evaluate_job(onsite_job, profile, policy, db)
        assert not eval_onsite.eligible
        assert "not_remote" in eval_onsite.failed_rules

        # Case 4: Eligible job meeting all criteria
        valid_job = Job(
            title=f"Senior Python Engineer {test_run_id} 4",
            company="Green Future Corp",
            location="Remote",
            remote=True,
            source="greenhouse",
            url=f"https://greenhouse.io/test/{test_run_id}",
            description="Looking for Senior Python Engineer with FastAPI and Docker skills."
        )
        db.add(valid_job)
        db.commit()
        db.refresh(valid_job)

        match = JobMatch(
            job_id=valid_job.id,
            score=88.0,
            skills_score=90.0,
            experience_score=85.0,
            role_score=95.0,
            location_score=100.0,
            education_score=90.0,
            responsibilities_score=85.0,
            strengths=["Python", "FastAPI"],
            gaps=[],
            explanation="Excellent fit"
        )
        db.add(match)
        db.commit()

        eval_valid = auto_apply_rules.evaluate_job(valid_job, profile, policy, db)
        assert eval_valid.eligible
        assert len(eval_valid.failed_rules) == 0


def test_auto_apply_quota_and_disabled_execution():
    with SessionLocal() as db:
        # Default policy is disabled
        policy = auto_apply_service.get_policy()
        policy.enabled = False
        auto_apply_service.update_policy(policy)

        quota_resp = client.get("/auto-apply/quota")
        assert quota_resp.status_code == 200
        quota_data = quota_resp.json()
        assert quota_data["policy_enabled"] is False
        assert quota_data["max_per_day"] == policy.max_applications_per_day

        # Trigger run without force_run -> must skip
        run_resp = client.post("/auto-apply/run", json={"force_run": False})
        assert run_resp.status_code == 200
        report = run_resp.json()
        assert report["status"] == "skipped"
        assert "disabled" in report["summary_message"]

        # If quota is 0, should reject with quota_exhausted
        policy.enabled = True
        policy.max_applications_per_day = 0
        auto_apply_service.update_policy(policy)

        quota_exhausted_resp = client.post("/auto-apply/run", json={"force_run": True})
        assert quota_exhausted_resp.status_code == 200
        exhausted_report = quota_exhausted_resp.json()
        assert exhausted_report["status"] == "quota_exhausted"


def test_auto_apply_safety_escalation_on_uncertainty():
    """
    CRITICAL SAFETY INVARIANT:
    If any question requires review or has confidence < 0.80,
    the pipeline MUST NOT submit the application. It must remain in 'READY' status
    and escalate to the user.
    """
    with SessionLocal() as db:
        test_run_id = str(uuid.uuid4())[:8]
        # Create Job
        job = Job(
            title=f"AI Engineer {test_run_id}",
            company="SafetyAI Corp",
            location="Remote",
            remote=True,
            source="greenhouse",
            url=f"https://safetyai.com/jobs/{test_run_id}",
            description="Lead ethical AI deployments. Python and ML governance required."
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Create Match Score high enough to qualify
        match = JobMatch(
            job_id=job.id,
            score=92.0,
            skills_score=90.0,
            experience_score=90.0,
            role_score=95.0,
            location_score=100.0,
            education_score=90.0,
            responsibilities_score=85.0,
            strengths=["Python", "FastAPI"],
            gaps=[],
            explanation="Strong fit"
        )
        db.add(match)
        db.commit()

        # Update policy to qualify this job
        policy = AutoApplyPolicy(
            enabled=True,
            minimum_match_score=85.0,
            target_roles=["AI Engineer"],
            max_applications_per_day=5,
            remote_only=True,
            require_all_skills_grounded=True
        )
        auto_apply_service.update_policy(policy)

        uncertain_question = ScreeningQuestion(
            id="clearance_q",
            prompt="Do you possess active Top Secret Security Clearance?",
            field_type="radio",
            selector="#clearance-q",
            required=True
        )
        uncertain_answer = QuestionAnswer(
            question_id="clearance_q",
            prompt="Do you possess active Top Secret Security Clearance?",
            answer="No",
            confidence=0.50,  # Below 0.80 safety threshold
            needs_review=True,
            review_reason="No security clearance information found in profile."
        )

        async def _mock_extract(db_sess, app_id):
            return [uncertain_question]

        async def _mock_prepare_draft(db_sess, job_id, profile=None, resume_file_path=None):
            app_inst = db_sess.query(Application).filter(Application.job_id == job_id).first()
            if not app_inst:
                app_inst = Application(
                    job_id=job_id,
                    status="READY",
                    application_url=job.url,
                    source=job.source,
                    filled_fields={"first_name": "Jane"},
                    unfilled_fields=[],
                    screening_questions=[uncertain_question.model_dump()],
                    answers={},
                    status_history=[]
                )
                db_sess.add(app_inst)
                db_sess.commit()
                db_sess.refresh(app_inst)
            return app_inst

        with patch.object(
            auto_apply_service, "_policy", policy
        ), patch(
            "backend.app.services.application_service.application_service.prepare_draft_for_job",
            side_effect=_mock_prepare_draft
        ), patch(
            "backend.app.services.application_service.application_service.extract_screening_questions",
            side_effect=_mock_extract
        ), patch(
            "backend.app.services.application_service.application_service.answer_screening_questions",
            return_value=[uncertain_answer]
        ), patch(
            "backend.app.services.application_service.application_service.submit_application"
        ) as mock_submit:

            resp = client.post("/auto-apply/run", json={"max_jobs": 1, "force_run": True})
            assert resp.status_code == 200
            data = resp.json()

            # Verify submission was NOT executed
            mock_submit.assert_not_called()

            # Verify escalation was logged in report
            assert data["escalated_count"] >= 1
            assert data["submitted_count"] == 0

            # Verify DB application record remains in READY status with escalation note
            app_record = db.query(Application).filter(Application.job_id == job.id).first()
            assert app_record is not None
            assert app_record.status == "READY"
            assert any("Auto-Apply Escalation" in (entry.get("note", "")) for entry in (app_record.status_history or []))


def test_analytics_overview_telemetry():
    with SessionLocal() as db:
        resp = client.get("/analytics/overview")
        assert resp.status_code == 200
        data = resp.json()

        # Check telemetry fields defined in SystemMetricsOverview
        assert "total_jobs" in data
        assert "total_applications" in data
        assert "funnel_breakdown" in data
        assert "submitted_count" in data
        assert "interview_count" in data
        assert "offer_count" in data
        assert "failed_count" in data
        assert "interview_conversion_rate" in data
        assert "offer_conversion_rate" in data
        assert "average_match_score" in data
        assert "source_distribution" in data
        assert "scheduler_active" in data
        assert "auto_apply_active" in data
        assert "daily_quota_used" in data
        assert "daily_quota_max" in data
        assert "generated_at" in data
