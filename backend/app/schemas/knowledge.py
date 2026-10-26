"""Company intelligence payloads: documents and memory."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus, FactSource
from app.schemas.common import ORMModel


class DocumentRead(ORMModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    created_at: datetime


class DocumentSummary(DocumentRead):
    chunk_count: int


class MemoryRead(ORMModel):
    id: uuid.UUID
    key: str
    value: str
    category: str | None
    source_kind: FactSource
    confidence: float | None
    superseded: bool
    confirmed_at: datetime | None
    origin_meeting_id: uuid.UUID | None
    origin_document_id: uuid.UUID | None
    created_at: datetime


class MemoryCreate(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=8000)
    category: str | None = Field(default=None, max_length=100)
    source_kind: FactSource = Field(
        default=FactSource.USER_CONFIRMED,
        description=(
            "Anything a person types here is user_confirmed by definition. "
            "Other values exist for facts the system records on their behalf."
        ),
    )


class MemoryCorrect(BaseModel):
    value: str = Field(min_length=1, max_length=8000)


class KnowledgeHitRead(BaseModel):
    source: str
    excerpt: str
    provenance: FactSource
    provenance_label: str
    is_verified: bool
    rank: float


class KnowledgeSearchRead(BaseModel):
    query: str
    hits: list[KnowledgeHitRead]
    verified_count: int
    note: str
