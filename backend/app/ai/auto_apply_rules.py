import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.models.application import Application
from backend.app.models.job import Job
from backend.app.models.match import JobMatch
from backend.app.models.resume import CandidateProfile


class AutoApplyPolicy(BaseModel):
    """
    Phase 48: Explicit, reviewable configuration for what the system may process automatically.
    """
    enabled: bool = Field(default=False, description="Master toggle for automated application processing")
    minimum_match_score: float = Field(default=80.0, ge=0.0, le=100.0, description="Minimum AI match score required to auto-apply")
    target_roles: List[str] = Field(
        default_factory=lambda: ["AI Engineer", "Python Developer", "Backend Engineer", "Full Stack Engineer"],
        description="Target job title keywords"
    )
    allowed_locations: List[str] = Field(
        default_factory=lambda: ["Remote", "India", "United States"],
        description="Permitted job locations"
    )
    remote_only: bool = Field(default=True, description="Strictly apply only to remote-tagged jobs")
    max_applications_per_day: int = Field(default=5, ge=1, le=50, description="Daily safety ceiling to prevent spamming")
    excluded_companies: List[str] = Field(default_factory=list, description="Companies to ignore completely")
    excluded_keywords: List[str] = Field(default_factory=list, description="Keywords in job description that disqualify the post")
    require_all_skills_grounded: bool = Field(
        default=True,
        description="Require 100% grounded screening answers with zero uncertainty flags"
    )


class EligibilityResult(BaseModel):
    eligible: bool
    job_id: int
    match_score: float
    reasons: List[str]
    failed_rules: List[str]
    rule_checks: Dict[str, bool]


class AutoApplyRulesEngine:
    """
    Phase 48: Evaluates whether a job posting satisfies configured criteria for automated processing.
    """

    def evaluate_job(
        self,
        job: Job,
        profile: CandidateProfile,
        policy: AutoApplyPolicy,
        db: Session
    ) -> EligibilityResult:
        reasons: List[str] = []
        failed_rules: List[str] = []
        rule_checks: Dict[str, bool] = {}

        # Rule 1: Exclude jobs already in draft or applied to
        existing_app = db.query(Application).filter(Application.job_id == job.id).first()
        if existing_app:
            failed_rules.append("already_applied")
            reasons.append(f"Job #{job.id} already has an application record with status '{existing_app.status}'.")
            rule_checks["not_already_applied"] = False
        else:
            rule_checks["not_already_applied"] = True

        # Rule 2: Excluded companies
        if policy.excluded_companies:
            excluded_lower = [c.lower() for c in policy.excluded_companies]
            if job.company.lower() in excluded_lower:
                failed_rules.append("excluded_company")
                reasons.append(f"Company '{job.company}' is in the excluded companies list.")
                rule_checks["company_allowed"] = False
            else:
                rule_checks["company_allowed"] = True
        else:
            rule_checks["company_allowed"] = True

        # Rule 2b: Excluded keywords in description
        if policy.excluded_keywords and job.description:
            desc_lower = job.description.lower()
            found_kw = [kw for kw in policy.excluded_keywords if kw.lower() in desc_lower]
            if found_kw:
                failed_rules.append("excluded_keyword")
                reasons.append(f"Job description contains excluded keyword(s): {', '.join(found_kw)}.")
                rule_checks["keywords_allowed"] = False
            else:
                rule_checks["keywords_allowed"] = True
        else:
            rule_checks["keywords_allowed"] = True

        # Rule 3: Match score threshold
        match_record = db.query(JobMatch).filter(JobMatch.job_id == job.id).first()
        match_score = float(match_record.score) if match_record else 0.0
        if match_score < policy.minimum_match_score:
            failed_rules.append("score_below_threshold")
            reasons.append(
                f"Match score ({match_score}%) is below minimum required threshold ({policy.minimum_match_score}%)."
            )
            rule_checks["score_threshold_met"] = False
        else:
            rule_checks["score_threshold_met"] = True

        # Rule 4: Target roles
        title_lower = job.title.lower()
        role_matched = False
        for target in policy.target_roles:
            if re.search(rf"\b{re.escape(target.lower())}\b", title_lower):
                role_matched = True
                break
        if not role_matched and policy.target_roles:
            failed_rules.append("role_not_targeted")
            reasons.append(f"Job title '{job.title}' does not match any configured target roles.")
            rule_checks["role_targeted"] = False
        else:
            rule_checks["role_targeted"] = True

        # Rule 5: Remote & location requirements
        if policy.remote_only and not job.remote:
            failed_rules.append("not_remote")
            reasons.append("Job is not marked as Remote, and policy specifies remote_only=True.")
            rule_checks["remote_allowed"] = False
        else:
            rule_checks["remote_allowed"] = True

        eligible = len(failed_rules) == 0
        if eligible:
            reasons.append(f"Job satisfies all rules with an AI match score of {match_score}%.")

        return EligibilityResult(
            eligible=eligible,
            job_id=job.id,
            match_score=match_score,
            reasons=reasons,
            failed_rules=failed_rules,
            rule_checks=rule_checks
        )


auto_apply_rules = AutoApplyRulesEngine()
