from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Index
)
from pydantic import BaseModel, Field, ConfigDict
from backend.app.db.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="READY", index=True)
    # Lifecycle: SAVED -> MATCHED -> READY -> APPROVED -> SUBMITTED (or REJECTED, INTERVIEW, OFFER, WITHDRAWN)
    
    application_url = Column(String(1024), nullable=False)
    source = Column(String(100), nullable=False, default="greenhouse")
    resume_version = Column(String(255), nullable=True)
    cover_letter = Column(Text, nullable=True)
    
    # Audit log of filled vs unfilled fields
    filled_fields = Column(JSON, nullable=False, default=dict)
    unfilled_fields = Column(JSON, nullable=False, default=list)
    answers = Column(JSON, nullable=False, default=dict)
    tailored_resume = Column(JSON, nullable=True)
    screening_questions = Column(JSON, nullable=True, default=list)

    approved_at = Column(DateTime(timezone=True), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    confirmation_details = Column(JSON, nullable=True)
    failure_reason = Column(Text, nullable=True)
    submission_screenshot = Column(String(512), nullable=True)

    # Lifecycle tracking & audit history
    status_history = Column(JSON, nullable=True, default=list)
    interview_details = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        Index("ix_applications_job_status", "job_id", "status"),
    )


# --- Pydantic Schemas ---

class ApplicationDraftResult(BaseModel):
    job_id: int
    status: str = "READY"
    application_url: str
    source: str
    filled_fields: Dict[str, Any] = Field(default_factory=dict)
    unfilled_fields: List[str] = Field(default_factory=list)
    resume_attached: bool = False
    stopped_before_submission: bool = True
    extracted_questions: List[Dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class SubmissionResult(BaseModel):
    application_id: int
    success: bool
    status: str
    confirmation_message: Optional[str] = None
    confirmation_url: Optional[str] = None
    screenshot_path: Optional[str] = None
    failure_reason: Optional[str] = None
    applied_at: Optional[datetime] = None


VALID_STATUSES = [
    "SAVED",
    "MATCHED",
    "READY",
    "APPROVED",
    "SUBMITTED",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
    "FAILED",
]


class StatusHistoryEntry(BaseModel):
    from_status: Optional[str] = None
    to_status: str
    timestamp: str
    actor: str = "user"
    note: Optional[str] = None
    interview_details: Optional[Dict[str, Any]] = None


class StatusUpdatePayload(BaseModel):
    status: str
    note: Optional[str] = None
    actor: str = "user"
    interview_details: Optional[Dict[str, Any]] = None


class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    status: str
    application_url: str
    source: str
    resume_version: Optional[str] = None
    cover_letter: Optional[str] = None
    filled_fields: Dict[str, Any]
    unfilled_fields: List[str]
    answers: Dict[str, Any]
    tailored_resume: Optional[Dict[str, Any]] = None
    screening_questions: List[Dict[str, Any]] = Field(default_factory=list)
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    confirmation_details: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    submission_screenshot: Optional[str] = None
    status_history: List[Dict[str, Any]] = Field(default_factory=list)
    interview_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationContentUpdate(BaseModel):
    filled_fields: Optional[Dict[str, Any]] = None
    cover_letter: Optional[str] = None
    answers: Optional[Dict[str, Any]] = None
    tailored_resume: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    interview_details: Optional[Dict[str, Any]] = None


class ApplicationListResponse(BaseModel):
    total: int
    items: List[ApplicationResponse]

