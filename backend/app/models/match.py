from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field, ConfigDict
from backend.app.db.database import Base


class JobMatch(Base):
    __tablename__ = "job_matches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False, index=True)  # Overall composite score 0-100
    skills_score = Column(Float, nullable=False, default=0.0)
    experience_score = Column(Float, nullable=False, default=0.0)
    role_score = Column(Float, nullable=False, default=0.0)
    location_score = Column(Float, nullable=False, default=0.0)
    education_score = Column(Float, nullable=False, default=0.0)
    responsibilities_score = Column(Float, nullable=False, default=0.0)
    
    strengths = Column(JSON, nullable=False, default=list)
    gaps = Column(JSON, nullable=False, default=list)
    explanation = Column(Text, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("job_id", name="uq_job_match_job_id"),
    )


# --- Pydantic Schemas ---

class MatchBreakdown(BaseModel):
    skills: float = Field(..., description="Skills alignment score (0-100), weight 35%")
    experience: float = Field(..., description="Experience level alignment (0-100), weight 20%")
    role: float = Field(..., description="Target role match (0-100), weight 20%")
    location: float = Field(..., description="Location & remote fit (0-100), weight 10%")
    responsibilities: float = Field(..., description="Responsibilities alignment (0-100), weight 10%")
    education: float = Field(..., description="Education requirement fit (0-100), weight 5%")


class JobMatchResponse(BaseModel):
    id: int
    job_id: int
    score: float
    breakdown: MatchBreakdown
    strengths: List[str]
    gaps: List[str]
    explanation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def format_job_match(match: JobMatch) -> JobMatchResponse:
    return JobMatchResponse(
        id=match.id,
        job_id=match.job_id,
        score=match.score,
        breakdown=MatchBreakdown(
            skills=match.skills_score,
            experience=match.experience_score,
            role=match.role_score,
            location=match.location_score,
            responsibilities=match.responsibilities_score,
            education=match.education_score
        ),
        strengths=match.strengths,
        gaps=match.gaps,
        explanation=match.explanation,
        created_at=match.created_at
    )
