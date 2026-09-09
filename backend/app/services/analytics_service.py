from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.scheduler import job_scheduler
from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.match import JobMatch
from backend.app.services.auto_apply_service import auto_apply_service


class SystemMetricsOverview(BaseModel):
    total_jobs: int = 0
    total_applications: int = 0
    funnel_breakdown: Dict[str, int] = Field(default_factory=dict)
    submitted_count: int = 0
    interview_count: int = 0
    offer_count: int = 0
    failed_count: int = 0
    interview_conversion_rate: float = 0.0
    offer_conversion_rate: float = 0.0
    average_match_score: float = 0.0
    source_distribution: Dict[str, int] = Field(default_factory=dict)
    scheduler_active: bool = False
    auto_apply_active: bool = False
    daily_quota_used: int = 0
    daily_quota_max: int = 5
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalyticsService:
    """
    Phase 50: Production telemetry, conversion funnel analytics, and operational metrics.
    """

    def get_overview_metrics(self, db: Session) -> SystemMetricsOverview:
        total_jobs = db.query(Job).count()
        total_applications = db.query(Application).count()

        # Funnel status breakdown
        status_counts_query = db.query(Application.status, func.count(Application.id)).group_by(Application.status).all()
        funnel_breakdown = {status: count for status, count in status_counts_query}

        submitted = funnel_breakdown.get("SUBMITTED", 0)
        interviews = funnel_breakdown.get("INTERVIEW", 0)
        offers = funnel_breakdown.get("OFFER", 0)
        failed = funnel_breakdown.get("FAILED", 0)

        # Total reach (submitted + progressed)
        total_active_pipeline = submitted + interviews + offers
        interview_rate = round((interviews + offers) / max(1, total_active_pipeline) * 100.0, 1) if total_active_pipeline else 0.0
        offer_rate = round(offers / max(1, total_active_pipeline) * 100.0, 1) if total_active_pipeline else 0.0

        # Average match score
        avg_score_res = db.query(func.avg(JobMatch.score)).scalar()
        avg_score = round(float(avg_score_res), 1) if avg_score_res is not None else 0.0

        # Sources distribution
        sources_query = db.query(Job.source, func.count(Job.id)).group_by(Job.source).all()
        source_dist = {src: count for src, count in sources_query}

        # Auto-apply quota
        policy = auto_apply_service.get_policy()
        daily_used = auto_apply_service.get_daily_submitted_count(db)

        return SystemMetricsOverview(
            total_jobs=total_jobs,
            total_applications=total_applications,
            funnel_breakdown=funnel_breakdown,
            submitted_count=submitted,
            interview_count=interviews,
            offer_count=offers,
            failed_count=failed,
            interview_conversion_rate=interview_rate,
            offer_conversion_rate=offer_rate,
            average_match_score=avg_score,
            source_distribution=source_dist,
            scheduler_active=job_scheduler.is_active,
            auto_apply_active=policy.enabled,
            daily_quota_used=daily_used,
            daily_quota_max=policy.max_applications_per_day
        )


analytics_service = AnalyticsService()
