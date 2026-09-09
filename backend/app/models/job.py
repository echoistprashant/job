from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index
)
from pydantic import BaseModel, Field, ConfigDict
from backend.app.db.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), nullable=True, default="Remote")
    remote = Column(Boolean, default=False, index=True)
    experience = Column(String(100), nullable=True, default="0-2 years")
    description = Column(Text, nullable=False)
    url = Column(String(1024), nullable=False, unique=True, index=True)
    source = Column(String(100), nullable=False, default="manual", index=True)
    external_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_source_external_id"),
        Index("ix_jobs_title_company", "title", "company"),
    )


# --- Pydantic Schemas ---

class JobBase(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "AI Engineer"})
    company: str = Field(..., json_schema_extra={"example": "ABC Technologies"})
    location: Optional[str] = Field(default="Remote", json_schema_extra={"example": "Bangalore, India"})
    remote: bool = Field(default=False, json_schema_extra={"example": True})
    experience: Optional[str] = Field(default="0-2 years", json_schema_extra={"example": "0-2 years"})
    description: str = Field(..., json_schema_extra={"example": "We are looking for an AI Engineer experienced in LLMs and FastAPI."})
    url: str = Field(..., json_schema_extra={"example": "https://boards.greenhouse.io/example/jobs/12345"})
    source: str = Field(default="manual", json_schema_extra={"example": "greenhouse"})
    external_id: Optional[str] = Field(default=None, json_schema_extra={"example": "gh_12345"})


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    total: int
    items: List[JobResponse]


class JobFilterParams(BaseModel):
    keyword: Optional[str] = None
    location: Optional[str] = None
    remote_only: Optional[bool] = None
    experience: Optional[str] = None
    source: Optional[str] = None
    limit: int = 50
    offset: int = 0
