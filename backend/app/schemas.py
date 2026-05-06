from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import JobStatus


class DocumentBase(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    status: JobStatus
    progress: int
    stage: str
    error_message: str | None
    is_finalized: bool
    attempts: int
    created_at: datetime
    updated_at: datetime


class DocumentOut(DocumentBase):
    id: int
    extracted_data: dict[str, Any] | None
    finalized_data: dict[str, Any] | None

    class Config:
        from_attributes = True


class UpdateDocumentPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class ProgressEvent(BaseModel):
    document_id: int
    event: str
    progress: int
    status: JobStatus
    message: str | None = None
