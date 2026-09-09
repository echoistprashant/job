from typing import List, Optional
from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    institution: str = Field(default="", description="Name of university, college, or school")
    degree: str = Field(default="", description="Degree level, e.g. B.Tech, B.S., M.S.")
    field_of_study: Optional[str] = Field(default=None, description="Major or field of study")
    start_date: Optional[str] = Field(default=None, description="Start date/year")
    end_date: Optional[str] = Field(default=None, description="End date/year or expected completion")
    grade: Optional[str] = Field(default=None, description="GPA or percentage if available")


class ExperienceItem(BaseModel):
    company: str = Field(default="", description="Company or organization name")
    role: str = Field(default="", description="Job title or role")
    location: Optional[str] = Field(default=None, description="Work location")
    start_date: Optional[str] = Field(default=None, description="Start date/year")
    end_date: Optional[str] = Field(default=None, description="End date/year or 'Present'")
    current: bool = Field(default=False, description="Whether this is the current job")
    description: str = Field(default="", description="Overview of duties and responsibilities")
    highlights: List[str] = Field(default_factory=list, description="Key bullet achievements")


class ProjectItem(BaseModel):
    title: str = Field(default="", description="Project title")
    description: str = Field(default="", description="Summary of project and impact")
    technologies: List[str] = Field(default_factory=list, description="Technologies/tools used")
    link: Optional[str] = Field(default=None, description="URL/repository link")


class CertificationItem(BaseModel):
    name: str = Field(default="", description="Certification name")
    issuer: Optional[str] = Field(default=None, description="Issuing organization")
    issue_date: Optional[str] = Field(default=None, description="Date issued")
    credential_id: Optional[str] = Field(default=None, description="License or credential ID")


class CandidateDetails(BaseModel):
    name: str = Field(default="Candidate", description="Full name of the candidate")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    location: Optional[str] = Field(default=None, description="Current location/city")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    github: Optional[str] = Field(default=None, description="GitHub or portfolio URL")
    summary: Optional[str] = Field(default=None, description="Professional summary / objective")
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    candidate: CandidateDetails = Field(default_factory=CandidateDetails)
    target_roles: List[str] = Field(
        default_factory=lambda: ["AI Engineer", "ML Engineer", "Backend Engineer"],
        description="Target job titles candidate is seeking"
    )
    experience_level: str = Field(
        default="Entry Level",
        description="Seniority level, e.g. Entry Level, Mid Level, Senior"
    )
    locations: List[str] = Field(
        default_factory=lambda: ["Remote"],
        description="Preferred geographic locations or remote options"
    )
    skills: List[str] = Field(
        default_factory=list,
        description="Consolidated primary skill list for quick matching"
    )
    remote_preference: bool = Field(
        default=True,
        description="Preference for remote positions"
    )
    minimum_match_score: int = Field(
        default=75,
        ge=0,
        le=100,
        description="Threshold minimum match score required for consideration"
    )
    auto_apply: bool = Field(
        default=False,
        description="Whether auto-apply is enabled (disabled by default during dev)"
    )


class ResumeUploadResponse(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int
    extracted_text_length: int
    profile: CandidateProfile


class CandidateProfileUpdate(BaseModel):
    target_roles: Optional[List[str]] = None
    experience_level: Optional[str] = None
    locations: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    remote_preference: Optional[bool] = None
    minimum_match_score: Optional[int] = Field(default=None, ge=0, le=100)
    auto_apply: Optional[bool] = None

