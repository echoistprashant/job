import math
import re
from typing import Dict, List, Optional, Tuple
from backend.app.models.job import Job
from backend.app.models.match import MatchBreakdown
from backend.app.models.resume import CandidateProfile


class RuleBasedMatcher:
    """Deterministic rule-based matcher for skills, roles, and experience."""

    def evaluate_skills(self, candidate_skills: List[str], job_text: str) -> Tuple[float, List[str], List[str]]:
        """Calculate skill overlap score (0-100), detected strengths, and missing gaps."""
        if not candidate_skills:
            return 0.0, [], []

        job_lower = job_text.lower()
        matched = []
        missing = []

        # Find candidate skills mentioned in the job description
        for skill in candidate_skills:
            if re.search(rf"\b{re.escape(skill.lower())}\b", job_lower):
                matched.append(skill)

        # Look for common industry skills mentioned in the job that candidate is missing
        from backend.app.ai.resume_parser import COMMON_TECH_SKILLS
        candidate_skills_lower = {s.lower() for s in candidate_skills}
        for common_skill in COMMON_TECH_SKILLS:
            if common_skill.lower() not in candidate_skills_lower:
                if re.search(rf"\b{re.escape(common_skill.lower())}\b", job_lower):
                    missing.append(common_skill)

        # Baseline skill score based on candidate skills present in job
        score = min(100.0, (len(matched) / max(1, len(candidate_skills) * 0.5)) * 100.0) if matched else 30.0
        return round(score, 1), matched, missing[:5]

    def evaluate_role(self, target_roles: List[str], job_title: str) -> float:
        """Calculate alignment between target roles and job title (0-100)."""
        job_title_lower = job_title.lower()
        for role in target_roles:
            role_lower = role.lower()
            if role_lower == job_title_lower:
                return 100.0
            if role_lower in job_title_lower or job_title_lower in role_lower:
                return 85.0
            # Token overlap
            role_tokens = set(role_lower.split())
            title_tokens = set(job_title_lower.split())
            overlap = role_tokens.intersection(title_tokens)
            if overlap:
                return min(100.0, (len(overlap) / max(len(role_tokens), len(title_tokens))) * 90.0)

        return 20.0

    def evaluate_location(self, candidate_locations: List[str], remote_pref: bool, job: Job) -> float:
        """Calculate location and remote compatibility (0-100)."""
        if job.remote and remote_pref:
            return 100.0

        job_loc_lower = (job.location or "").lower()
        for loc in candidate_locations:
            if loc.lower() in job_loc_lower or job_loc_lower in loc.lower():
                return 95.0

        return 40.0 if not job.remote else 80.0

    def evaluate_experience(self, candidate_level: str, job_experience: Optional[str]) -> float:
        """Calculate seniority / experience alignment (0-100)."""
        if not job_experience:
            return 80.0

        exp_lower = job_experience.lower()
        cand_lower = candidate_level.lower()

        if "entry" in cand_lower or "junior" in cand_lower:
            if "0-1" in exp_lower or "0-2" in exp_lower or "entry" in exp_lower or "junior" in exp_lower:
                return 100.0
            elif "1-3" in exp_lower or "2-4" in exp_lower:
                return 75.0
            elif "5+" in exp_lower or "senior" in exp_lower or "lead" in exp_lower:
                return 30.0

        if "mid" in cand_lower:
            if "2-4" in exp_lower or "3-5" in exp_lower or "mid" in exp_lower:
                return 100.0
            return 80.0

        if "senior" in cand_lower:
            if "5+" in exp_lower or "senior" in exp_lower or "lead" in exp_lower:
                return 100.0
            return 70.0

        return 75.0


class SemanticMatcher:
    """Computes vector space representations and cosine similarity."""

    def _tokenize(self, text: str) -> List[str]:
        return [t for t in re.findall(r"\b[a-zA-Z0-9_\-\.\#\+]{2,}\b", text.lower()) if len(t) > 2]

    def _get_vector(self, text: str) -> Dict[str, float]:
        tokens = self._tokenize(text)
        freq: Dict[str, float] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0.0) + 1.0
        # Normalize vector to unit length
        norm = math.sqrt(sum(v * v for v in freq.values()))
        if norm > 0:
            for k in freq:
                freq[k] /= norm
        return freq

    def calculate_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two documents (returns 0.0 to 100.0)."""
        vec_a = self._get_vector(text_a)
        vec_b = self._get_vector(text_b)

        # Dot product of normalized vectors
        similarity = 0.0
        for token, val_a in vec_a.items():
            if token in vec_b:
                similarity += val_a * vec_b[token]

        # Scale 0.0-1.0 to 0.0-100.0 with non-linear boost for meaningful technical overlap
        score = min(100.0, math.sqrt(max(0.0, similarity)) * 100.0)
        return round(score, 1)


class LLMMatchReasoner:
    """Generates structured qualitative explanation, strengths, and gaps."""

    def generate_reasoning(
        self,
        candidate_skills: List[str],
        matched_skills: List[str],
        missing_skills: List[str],
        job: Job,
        overall_score: float
    ) -> Tuple[List[str], List[str], str]:
        strengths = []
        for s in matched_skills[:4]:
            strengths.append(f"Strong match for required skill: {s}")
        if job.remote:
            strengths.append("Position offers remote work aligning with candidate preference")
        if not strengths:
            strengths.append(f"Foundation in software engineering relevant to {job.title}")

        gaps = []
        for m in missing_skills[:3]:
            gaps.append(f"Preferred skill mentioned in job posting: {m}")
        if not gaps:
            gaps.append("None identified - comprehensive match for role criteria")

        # Grounded summary explanation
        matched_str = ", ".join(matched_skills[:3]) if matched_skills else "general tech background"
        gap_str = f" However, knowledge in {', '.join(missing_skills[:2])} could further improve standing." if missing_skills else ""
        explanation = (
            f"Candidate displays a {overall_score:.1f}% fit for {job.title} at {job.company}. "
            f"Key matching competencies include {matched_str}.{gap_str}"
        )

        return strengths, gaps, explanation


class HybridJobMatcher:
    """
    Combines deterministic rules, semantic similarity, and LLM reasoning.
    Weighted dimensions:
      - Skills: 35%
      - Experience: 20%
      - Role: 20%
      - Location: 10%
      - Responsibilities: 10%
      - Education: 5%
    """

    def __init__(self):
        self.rule_matcher = RuleBasedMatcher()
        self.semantic_matcher = SemanticMatcher()
        self.reasoner = LLMMatchReasoner()

    def match(self, profile: CandidateProfile, job: Job) -> Tuple[float, MatchBreakdown, List[str], List[str], str]:
        job_full_text = f"{job.title}\n{job.description}\n{job.company}\n{job.location or ''}"
        candidate_full_text = (
            f"{' '.join(profile.target_roles)}\n"
            f"{' '.join(profile.skills)}\n"
            f"{profile.candidate.summary or ''}\n"
            f"{' '.join([p.description for p in profile.candidate.projects])}"
        )

        # 1. Skills (35%)
        skills_score, matched_skills, missing_skills = self.rule_matcher.evaluate_skills(
            profile.skills or profile.candidate.skills,
            job_full_text
        )

        # 2. Experience (20%)
        experience_score = self.rule_matcher.evaluate_experience(
            profile.experience_level,
            job.experience
        )

        # 3. Role (20%)
        role_score = self.rule_matcher.evaluate_role(
            profile.target_roles,
            job.title
        )

        # 4. Location (10%)
        location_score = self.rule_matcher.evaluate_location(
            profile.locations,
            profile.remote_preference,
            job
        )

        # 5. Responsibilities (10%) - evaluated via semantic cosine similarity
        responsibilities_score = self.semantic_matcher.calculate_similarity(
            candidate_full_text,
            job.description
        )

        # 6. Education (5%)
        education_score = 90.0 if profile.candidate.education else 60.0

        # Weighted composite score calculation
        composite_score = (
            0.35 * skills_score +
            0.20 * experience_score +
            0.20 * role_score +
            0.10 * location_score +
            0.10 * responsibilities_score +
            0.05 * education_score
        )
        composite_score = round(min(100.0, max(0.0, composite_score)), 1)

        breakdown = MatchBreakdown(
            skills=round(skills_score, 1),
            experience=round(experience_score, 1),
            role=round(role_score, 1),
            location=round(location_score, 1),
            responsibilities=round(responsibilities_score, 1),
            education=round(education_score, 1)
        )

        # Qualitative reasoning
        strengths, gaps, explanation = self.reasoner.generate_reasoning(
            candidate_skills=profile.skills or profile.candidate.skills,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            job=job,
            overall_score=composite_score
        )

        return composite_score, breakdown, strengths, gaps, explanation


hybrid_matcher = HybridJobMatcher()
