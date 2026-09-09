import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.models.job import Job
from backend.app.models.resume import (
    CandidateProfile,
    EducationItem,
    ExperienceItem,
    ProjectItem,
)


class TailoredResume(BaseModel):
    version_id: str
    job_id: Optional[int] = None
    company_name: str
    target_role: str
    headline: str
    tailored_summary: str
    highlighted_skills: List[str]
    secondary_skills: List[str]
    reordered_experiences: List[Dict[str, Any]]
    reordered_projects: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    factual_integrity_verified: bool = True
    created_at_epoch: float = Field(default_factory=time.time)


class ResumeTailor:
    """
    Phase 34: Resume Tailoring Agent.
    Generates job-specific resume drafts highlighting relevant skills, projects,
    and responsibilities for a target position while rigorously maintaining
    factual integrity and preventing any credential hallucination.
    """

    def tailor_resume(self, profile: CandidateProfile, job: Job) -> TailoredResume:
        job_text = f"{job.title} {job.description} {job.company}".lower()

        # 1. Skill alignment & re-ranking
        # Partition existing candidate skills into highlighted (matching job) vs secondary
        highlighted_skills: List[str] = []
        secondary_skills: List[str] = []

        for skill in profile.skills:
            if re.search(rf"\b{re.escape(skill.lower())}\b", job_text):
                highlighted_skills.append(skill)
            else:
                secondary_skills.append(skill)

        # Ensure at least top skills are present in highlighted if no direct matches
        if not highlighted_skills and profile.skills:
            highlighted_skills = profile.skills[:4]
            secondary_skills = profile.skills[4:]

        # 2. Headline & Tailored Summary
        top_skill_str = ", ".join(highlighted_skills[:3]) if highlighted_skills else "Software Engineering"
        headline = f"{job.title} | Specializing in {top_skill_str}"

        years = max(1, len(profile.candidate.experience) * 2)
        cand_name = profile.candidate.name or "Software Engineer"
        cand_summary = profile.candidate.summary or "Engineering professional with demonstrated expertise in delivering scalable systems."

        tailored_summary = (
            f"{cand_summary.rstrip('.')} "
            f"Focused on leveraging {top_skill_str} to drive impact as {job.title} at {job.company}."
        )

        # 3. Project scoring and reordering
        # Score each project by keyword overlap with job
        scored_projects: List[tuple[float, ProjectItem]] = []
        for proj in profile.candidate.projects:
            score = 0.0
            proj_text = f"{proj.title} {proj.description} {' '.join(proj.technologies)}".lower()
            for skill in highlighted_skills:
                if skill.lower() in proj_text:
                    score += 2.0
            for word in job.title.lower().split():
                if len(word) > 3 and word in proj_text:
                    score += 1.5
            scored_projects.append((score, proj))

        scored_projects.sort(key=lambda x: x[0], reverse=True)
        reordered_projects = [
            {
                "name": p.title,
                "description": p.description,
                "technologies": p.technologies,
                "url": p.link,
                "relevance_score": round(score, 1)
            }
            for score, p in scored_projects
        ]

        # 4. Experience scoring and reordering
        scored_exps: List[tuple[float, ExperienceItem]] = []
        for exp in profile.candidate.experience:
            score = 0.0
            exp_text = f"{exp.role} {exp.company} {exp.description or ''}".lower()
            for skill in highlighted_skills:
                if skill.lower() in exp_text:
                    score += 2.0
            scored_exps.append((score, exp))

        # Experiences are listed with relevance metadata while maintaining factual integrity
        scored_exps.sort(key=lambda x: x[0], reverse=True)
        reordered_experiences = [
            {
                "title": exp.role,
                "company": exp.company,
                "start_date": exp.start_date,
                "end_date": exp.end_date,
                "description": exp.description,
                "is_current": exp.current,
                "relevance_score": round(score, 1)
            }
            for score, exp in scored_exps
        ]

        # 5. Education preservation
        preserved_education = [
            {
                "degree": edu.degree,
                "institution": edu.institution,
                "year": edu.end_date or edu.start_date or ""
            }
            for edu in profile.candidate.education
        ]

        # 6. Factual Integrity Verification
        # Invariant check: all highlighted skills MUST come from profile.skills
        skills_set = set(profile.skills)
        skills_valid = all(s in skills_set for s in highlighted_skills)

        # Invariant check: all companies and institutions must match original exactly
        orig_companies = {e.company for e in profile.candidate.experience}
        tailored_companies = {e["company"] for e in reordered_experiences}
        companies_valid = (orig_companies == tailored_companies)

        orig_institutions = {edu.institution for edu in profile.candidate.education}
        tailored_institutions = {edu["institution"] for edu in preserved_education}
        institutions_valid = (orig_institutions == tailored_institutions)

        factual_integrity_verified = (skills_valid and companies_valid and institutions_valid)

        version_id = f"tailored_job_{job.id or 0}_{int(time.time())}"

        return TailoredResume(
            version_id=version_id,
            job_id=job.id,
            company_name=job.company,
            target_role=job.title,
            headline=headline,
            tailored_summary=tailored_summary,
            highlighted_skills=highlighted_skills,
            secondary_skills=secondary_skills,
            reordered_experiences=reordered_experiences,
            reordered_projects=reordered_projects,
            education=preserved_education,
            factual_integrity_verified=factual_integrity_verified
        )


resume_tailor = ResumeTailor()
