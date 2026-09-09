import re
from typing import List, Optional
from backend.app.models.resume import (
    CandidateProfile,
    CandidateDetails,
    EducationItem,
    ExperienceItem,
    ProjectItem,
    CertificationItem
)


COMMON_TECH_SKILLS = [
    "Python", "FastAPI", "Django", "Flask", "SQLAlchemy", "Pydantic",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "pgvector",
    "Machine Learning", "Deep Learning", "LLM", "NLP", "RAG", "LangChain",
    "LangGraph", "PyTorch", "TensorFlow", "Scikit-Learn", "HuggingFace",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Git", "GitHub", "CI/CD",
    "Linux", "Playwright", "Selenium", "JavaScript", "TypeScript", "React",
    "Next.js", "Node.js", "HTML", "CSS", "REST API", "GraphQL", "Microservices"
]


class ResumeParser:
    """Parses raw text into a structured CandidateProfile schema."""

    def parse(self, text: str) -> CandidateProfile:
        """Parse raw resume text into CandidateProfile."""
        # Clean text
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        email = self._extract_email(text)
        phone = self._extract_phone(text)
        linkedin = self._extract_url(text, r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+")
        github = self._extract_url(text, r"https?://(?:www\.)?github\.com/[\w\-]+")
        name = self._extract_name(lines, email)
        skills = self._extract_skills(text)
        education = self._extract_education(text)
        experience = self._extract_experience(text)
        projects = self._extract_projects(text)
        certifications = self._extract_certifications(text)

        # Derive candidate details
        candidate = CandidateDetails(
            name=name,
            email=email,
            phone=phone,
            linkedin=linkedin,
            github=github,
            summary=lines[1] if len(lines) > 1 and len(lines[1]) > 30 else None,
            skills=skills,
            education=education,
            experience=experience,
            projects=projects,
            certifications=certifications
        )

        # Derive target roles based on detected skills
        target_roles = self._derive_target_roles(skills, experience)

        return CandidateProfile(
            candidate=candidate,
            target_roles=target_roles,
            experience_level="Entry Level" if len(experience) <= 1 else "Mid Level",
            locations=["Remote", "India"],
            skills=skills,
            remote_preference=True,
            minimum_match_score=75,
            auto_apply=False
        )

    def _extract_email(self, text: str) -> Optional[str]:
        match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
        return match.group(0) if match else None

    def _extract_url(self, text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0) if match else None

    def _extract_name(self, lines: List[str], email: Optional[str]) -> str:
        if not lines:
            return "Candidate"
        
        # Usually the candidate's name is on line 1 or line 2, short, not an email or phone
        for line in lines[:3]:
            if "@" not in line and not re.search(r"\d{4}", line) and len(line.split()) <= 4:
                # Clean punctuation
                cleaned = re.sub(r"[^\w\s]", "", line).strip()
                if cleaned and len(cleaned) > 2:
                    return cleaned

        if email:
            # Fallback name from email username
            local_part = email.split("@")[0]
            clean_name = " ".join([p.capitalize() for p in re.split(r"[._-]", local_part) if p.isalpha()])
            if clean_name:
                return clean_name

        return "Candidate"

    def _extract_skills(self, text: str) -> List[str]:
        found_skills = []
        lower_text = f" {text.lower()} "
        for skill in COMMON_TECH_SKILLS:
            pattern = rf"\b{re.escape(skill.lower())}\b"
            if re.search(pattern, lower_text):
                found_skills.append(skill)
        return found_skills

    def _extract_education(self, text: str) -> List[EducationItem]:
        items = []
        edu_patterns = [
            (r"(?i)(b\.?tech|b\.?s\.?|bachelor(?:'s)?)\s*(?:in\s*)?([^\n,\.]+)?", "Bachelor's Degree"),
            (r"(?i)(m\.?tech|m\.?s\.?|master(?:'s)?)\s*(?:in\s*)?([^\n,\.]+)?", "Master's Degree"),
            (r"(?i)(ph\.?d\.?|doctorate)\s*(?:in\s*)?([^\n,\.]+)?", "Doctorate")
        ]
        
        for pat, degree_title in edu_patterns:
            matches = re.finditer(pat, text)
            for m in matches:
                field = m.group(2).strip() if m.group(2) else "Computer Science / Engineering"
                items.append(
                    EducationItem(
                        institution="University / Institute",
                        degree=degree_title,
                        field_of_study=field
                    )
                )

        if not items:
            items.append(
                EducationItem(
                    institution="University",
                    degree="Bachelor of Technology",
                    field_of_study="Computer Science and Engineering"
                )
            )
        return items

    def _extract_experience(self, text: str) -> List[ExperienceItem]:
        items = []
        # Look for role keywords followed by company or dates
        role_matches = re.finditer(
            r"(?i)(software engineer|backend engineer|full stack engineer|ai engineer|machine learning engineer|intern)\s+(?:at|@)\s+([A-Za-z0-9\s]+)",
            text
        )
        for m in role_matches:
            role = m.group(1).title()
            company = m.group(2).strip().split("\n")[0]
            items.append(
                ExperienceItem(
                    company=company,
                    role=role,
                    description=f"Worked as {role} at {company}",
                    highlights=[]
                )
            )

        return items

    def _extract_projects(self, text: str) -> List[ProjectItem]:
        projects = []
        proj_matches = re.finditer(
            r"(?i)project[:\s]+([^\n]+)",
            text
        )
        for m in proj_matches:
            title = m.group(1).strip()
            if len(title) > 3 and len(title) < 80:
                projects.append(
                    ProjectItem(
                        title=title,
                        description=f"Developed {title}",
                        technologies=[]
                    )
                )
        return projects

    def _extract_certifications(self, text: str) -> List[CertificationItem]:
        certifications = []
        cert_matches = re.finditer(
            r"(?i)certified\s+([^\n,]+)",
            text
        )
        for m in cert_matches:
            name = f"Certified {m.group(1).strip()}"
            certifications.append(CertificationItem(name=name))
        return certifications

    def _derive_target_roles(self, skills: List[str], experience: List[ExperienceItem]) -> List[str]:
        roles = []
        skills_set = set(skills)
        if {"LLM", "RAG", "LangChain", "PyTorch", "NLP"}.intersection(skills_set):
            roles.append("AI Engineer")
            roles.append("ML Engineer")
        if {"Python", "FastAPI", "SQLAlchemy", "PostgreSQL", "Docker"}.intersection(skills_set):
            roles.append("Backend Engineer")
        if {"React", "Next.js", "JavaScript", "TypeScript"}.intersection(skills_set):
            roles.append("Full Stack Engineer")
        
        if not roles:
            roles = ["AI Engineer", "ML Engineer", "Backend Engineer"]
        return list(dict.fromkeys(roles))


resume_parser = ResumeParser()
