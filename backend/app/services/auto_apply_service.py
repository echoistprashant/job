import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.ai.auto_apply_rules import AutoApplyPolicy, auto_apply_rules
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.match import JobMatch
from backend.app.models.resume import CandidateProfile
from backend.app.services.application_service import application_service
from backend.app.services.resume_service import resume_service

logger = logging.getLogger(__name__)


class AutoApplyCycleReport(BaseModel):
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    evaluated_count: int = 0
    submitted_count: int = 0
    escalated_count: int = 0
    skipped_count: int = 0
    daily_quota_remaining: int = 0
    summary_message: str = ""
    job_results: List[Dict[str, Any]] = Field(default_factory=list)


class AutoApplyService:
    """
    Phase 49: Controlled Auto-Apply execution pipeline with strict safety gates.
    """

    def __init__(self):
        self._policy = AutoApplyPolicy()

    def get_policy(self) -> AutoApplyPolicy:
        return self._policy

    def update_policy(self, new_policy: AutoApplyPolicy) -> AutoApplyPolicy:
        self._policy = new_policy
        logger.info(f"[AutoApply] Policy updated: enabled={new_policy.enabled}, min_score={new_policy.minimum_match_score}")
        return self._policy

    def get_daily_submitted_count(self, db: Session) -> int:
        """Count applications submitted today (UTC)."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return db.query(Application).filter(
            Application.status == "SUBMITTED",
            Application.applied_at >= today_start
        ).count()

    async def run_auto_apply_cycle(
        self,
        db: Session,
        max_jobs: Optional[int] = None,
        force_run: bool = False
    ) -> AutoApplyCycleReport:
        start_time = datetime.now(timezone.utc)
        policy = self._policy

        if not policy.enabled and not force_run:
            return AutoApplyCycleReport(
                status="skipped",
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                summary_message="Auto-apply is currently disabled in policy. Enable it to run automatically."
            )

        daily_submitted = self.get_daily_submitted_count(db)
        remaining_quota = max(0, policy.max_applications_per_day - daily_submitted)

        if remaining_quota <= 0:
            return AutoApplyCycleReport(
                status="quota_exhausted",
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                daily_quota_remaining=0,
                summary_message=f"Daily submission limit ({policy.max_applications_per_day}) already reached today."
            )

        profile = resume_service.get_current_profile() or CandidateProfile()

        # Query jobs that have been scored
        high_match_jobs = (
            db.query(Job, JobMatch.score)
            .join(JobMatch, Job.id == JobMatch.job_id)
            .filter(JobMatch.score >= policy.minimum_match_score)
            .order_by(JobMatch.score.desc())
            .all()
        )

        report = AutoApplyCycleReport(
            status="running",
            started_at=start_time,
            daily_quota_remaining=remaining_quota
        )

        limit_to_process = min(remaining_quota, max_jobs or remaining_quota)

        for job, score in high_match_jobs:
            if report.submitted_count >= limit_to_process:
                break

            report.evaluated_count += 1
            eligibility = auto_apply_rules.evaluate_job(job, profile, policy, db)

            if not eligibility.eligible:
                report.skipped_count += 1
                report.job_results.append({
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "action": "skipped",
                    "reasons": eligibility.reasons
                })
                continue

            # Safe execution: prepare draft
            try:
                app_record = await application_service.prepare_draft_for_job(db, job.id, profile)

                # Extract and answer questions
                questions = await application_service.extract_screening_questions(db, app_record.id)
                answers = application_service.answer_screening_questions(db, app_record.id, questions, profile)
                application_service.generate_tailored_resume(db, app_record.id, profile=profile)
                application_service.generate_cover_letter(db, app_record.id, profile=profile)

                # SAFETY GATE: Check for questions requiring review or low confidence
                uncertain_flags = []
                for ans in answers:
                    if ans.needs_review or ans.confidence < 0.80:
                        reason = getattr(ans, "review_reason", None) or getattr(ans, "rationale", None) or "Low confidence / unverified"
                        uncertain_flags.append(f"{ans.question_id}: {reason}")

                if uncertain_flags and policy.require_all_skills_grounded:
                    # Halt before submission - escalate to user
                    note = f"Auto-Apply Escalation: Requires human approval. Reasons: {'; '.join(uncertain_flags)}"
                    application_service.update_application_status(
                        db=db,
                        app_id=app_record.id,
                        new_status="READY",
                        note=note,
                        actor="auto_apply_policy"
                    )
                    report.escalated_count += 1
                    report.job_results.append({
                        "job_id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "action": "escalated_to_human",
                        "application_id": app_record.id,
                        "reasons": uncertain_flags
                    })
                else:
                    # 100% confident & grounded: Approve and submit
                    application_service.approve_application(
                        db=db,
                        app_id=app_record.id,
                        note=f"Auto-approved: Satisfied all policy rules with AI match score {score}%"
                    )
                    sub_result = await application_service.submit_application(db, app_record.id)

                    if sub_result.success:
                        report.submitted_count += 1
                        report.job_results.append({
                            "job_id": job.id,
                            "title": job.title,
                            "company": job.company,
                            "action": "submitted",
                            "application_id": app_record.id,
                            "score": score
                        })
                    else:
                        report.job_results.append({
                            "job_id": job.id,
                            "title": job.title,
                            "company": job.company,
                            "action": "failed",
                            "application_id": app_record.id,
                            "reason": sub_result.failure_reason
                        })
            except Exception as e:
                logger.error(f"[AutoApply] Error processing job {job.id}: {e}", exc_info=True)
                report.job_results.append({
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "action": "error",
                    "reason": str(e)
                })

        end_time = datetime.now(timezone.utc)
        report.completed_at = end_time
        report.status = "completed"
        report.daily_quota_remaining = max(0, policy.max_applications_per_day - (daily_submitted + report.submitted_count))
        report.summary_message = (
            f"Evaluated {report.evaluated_count} jobs: submitted {report.submitted_count}, "
            f"escalated {report.escalated_count} for human review, skipped {report.skipped_count}."
        )

        return report


auto_apply_service = AutoApplyService()
