import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.models.job import Job
from backend.app.models.resume import CandidateProfile


class CoverLetterDraft(BaseModel):
    job_id: Optional[int] = None
    company: str
    role: str
    salutation: str
    opening: str
    body_paragraphs: List[str]
    closing: str
    full_text: str
    grounded_skills: List[str] = Field(default_factory=list)
    grounded_projects: List[str] = Field(default_factory=list)


class CoverLetterGenerator:
    """
    Phase 35: Cover Letter Generation.
    Generates tailored, concise, grounded role-specific cover letters that connect
    candidate credentials to employer job requirements without hallucinations.
    Supports user editing and persistence.
    """

    def generate(
        self,
        profile: CandidateProfile,
        job: Job,
        custom_tone: str = "professional"
    ) -> CoverLetterDraft:
        company = job.company or "Hiring Team"
        role = job.title or "Position"
        cand_name = profile.candidate.name or "Applicant"
        job_text = f"{job.title} {job.description}".lower()

        # Identify candidate skills that directly match the job description
        matching_skills = []
        for skill in profile.skills:
            if re.search(rf"\b{re.escape(skill.lower())}\b", job_text):
                matching_skills.append(skill)

        if not matching_skills and profile.skills:
            matching_skills = profile.skills[:3]

        # Find most relevant project or experience
        top_project = None
        for p in profile.candidate.projects:
            if any(s.lower() in f"{p.title} {p.description} {' '.join(p.technologies)}".lower() for s in matching_skills):
                top_project = p
                break
        if not top_project and profile.candidate.projects:
            top_project = profile.candidate.projects[0]

        top_exp = None
        if profile.candidate.experience:
            top_exp = profile.candidate.experience[0]

        # Try Groq LLM generation first if configured
        from backend.app.ai.llm_client import llm_client

        if llm_client.is_configured:
            cand_exp_summary = "; ".join([f"{e.role} at {e.company}: {e.description}" for e in profile.candidate.experience[:2]])
            cand_proj_summary = "; ".join([f"{p.title}: {p.description}" for p in profile.candidate.projects[:2]])
            prompt = (
                f"Write a highly tailored, professional, and convincing cover letter for an applicant.\n"
                f"Applicant Name: {cand_name}\n"
                f"Target Role: {role}\n"
                f"Target Company: {company}\n"
                f"Candidate Skills: {', '.join(profile.skills[:8])}\n"
                f"Candidate Experience: {cand_exp_summary}\n"
                f"Candidate Projects: {cand_proj_summary}\n"
                f"Job Details: {job.description[:700]}\n"
                f"Tone: {custom_tone}\n\n"
                f"Output MUST be valid JSON with keys:\n"
                f"- 'salutation': string (e.g. 'Dear {company} Hiring Team,')\n"
                f"- 'opening': string (strong hook expressing excitement and fit)\n"
                f"- 'body_paragraphs': list of 2 strings (concrete accomplishments and value alignment)\n"
                f"- 'closing': string (call to action, thank you, and sign-off)\n"
                f"Do not invent false certifications or degrees. Respond ONLY in valid JSON."
            )
            llm_result = llm_client.chat_json([
                {"role": "system", "content": "You are an executive career strategist writing authentic, high-converting cover letters."},
                {"role": "user", "content": prompt}
            ])
            if llm_result and isinstance(llm_result, dict):
                salutation = llm_result.get("salutation", f"Dear {company} Hiring Team,")
                opening = llm_result.get("opening", "")
                body_paragraphs = llm_result.get("body_paragraphs", [])
                closing = llm_result.get("closing", f"Sincerely,\n{cand_name}")
                if opening and body_paragraphs and isinstance(body_paragraphs, list):
                    full_text = f"{salutation}\n\n{opening}\n\n" + "\n\n".join(body_paragraphs) + f"\n\n{closing}"
                    return CoverLetterDraft(
                        job_id=job.id,
                        company=company,
                        role=role,
                        salutation=salutation,
                        opening=opening,
                        body_paragraphs=body_paragraphs,
                        closing=closing,
                        full_text=full_text,
                        grounded_skills=matching_skills,
                        grounded_projects=[top_project.title] if top_project else []
                    )

        # Structure parts
        salutation = f"Dear {company} Hiring Team,"

        top_skills_str = ", ".join(matching_skills[:3]) if matching_skills else "software engineering"
        opening = (
            f"I am writing to express my enthusiasm for the {role} role at {company}. "
            f"With a strong background in {top_skills_str} and a track record of building dependable, "
            f"scalable software solutions, I am eager to contribute to your team's ongoing initiatives."
        )

        body_paragraphs = []

        # Paragraph 1: Experience & Project grounding
        if top_project:
            tech_str = ", ".join(top_project.technologies[:3]) if top_project.technologies else top_skills_str
            body_paragraphs.append(
                f"Throughout my work, I have consistently focused on delivering measurable engineering impact. "
                f"For example, in my project '{top_project.title}', I utilized {tech_str} to "
                f"{top_project.description.rstrip('.')}. This experience directly prepared me to solve the technical "
                f"challenges outlined in your job requirements for {role}."
            )
        elif top_exp:
            body_paragraphs.append(
                f"In my role as {top_exp.role} at {top_exp.company}, I {top_exp.description.rstrip('.')}. "
                f"This reinforced my ability to collaborate cross-functionally and deliver resilient backend systems under tight deadlines."
            )

        # Paragraph 2: Value proposition & alignment
        body_paragraphs.append(
            f"What particularly attracts me to {company} is your commitment to technical excellence and product innovation. "
            f"I am confident that my technical proficiency in {top_skills_str}, combined with my collaborative problem-solving "
            f"approach, will make me an immediate and valuable asset to your engineering organization."
        )

        closing = (
            f"Thank you for your time and consideration. I welcome the opportunity to discuss how my experience and skills "
            f"can help {company} achieve its goals. I look forward to speaking with you soon.\n\n"
            f"Sincerely,\n{cand_name}"
        )

        # Assemble full text
        full_text = f"{salutation}\n\n{opening}\n\n" + "\n\n".join(body_paragraphs) + f"\n\n{closing}"

        grounded_projects = [top_project.title] if top_project else []

        return CoverLetterDraft(
            job_id=job.id,
            company=company,
            role=role,
            salutation=salutation,
            opening=opening,
            body_paragraphs=body_paragraphs,
            closing=closing,
            full_text=full_text,
            grounded_skills=matching_skills,
            grounded_projects=grounded_projects
        )


cover_letter_generator = CoverLetterGenerator()
