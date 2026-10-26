"""Company intelligence: documents, memory, and knowledge search."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentOrg, CurrentUser, DbSession
from app.core.config import settings
from app.models.document import Document
from app.models.enums import FactSource
from app.schemas.knowledge import (
    DocumentRead,
    DocumentSummary,
    KnowledgeHitRead,
    KnowledgeSearchRead,
    MemoryCorrect,
    MemoryCreate,
    MemoryRead,
)
from app.services import ingestion, knowledge

router = APIRouter(tags=["company-intelligence"])


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


@router.post("/documents", response_model=DocumentSummary, status_code=201)
async def upload_document(
    org: CurrentOrg,
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
) -> DocumentSummary:
    """Upload and index a PDF, DOCX, or text file.

    The body is read with a hard cap before anything parses it, so an
    oversized upload costs memory proportional to the limit rather than to
    the file.
    """
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_bytes // 1_048_576} MB limit.",
        )

    try:
        document = await ingestion.ingest_document(
            db,
            organization_id=org.id,
            user_id=user.id,
            filename=file.filename or "upload",
            content_type=file.content_type or "",
            data=data,
        )
    except ingestion.IngestionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    docs = await ingestion.list_documents(db, org.id)
    chunk_count = next((c for d, c in docs if d.id == document.id), 0)

    return DocumentSummary(
        **DocumentRead.model_validate(document).model_dump(), chunk_count=chunk_count
    )


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(org: CurrentOrg, db: DbSession) -> list[DocumentSummary]:
    rows = await ingestion.list_documents(db, org.id)
    return [
        DocumentSummary(
            **DocumentRead.model_validate(doc).model_dump(), chunk_count=count
        )
        for doc, count in rows
    ]


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID, org: CurrentOrg, db: DbSession
) -> None:
    document = await db.get(Document, document_id)
    if (
        document is None
        or document.organization_id != org.id
        or document.deleted_at is not None
    ):
        raise HTTPException(status_code=404, detail="Document not found")
    await ingestion.delete_document(db, document)


# --------------------------------------------------------------------------
# Memory
# --------------------------------------------------------------------------


@router.get("/memory", response_model=list[MemoryRead])
async def list_memory(
    org: CurrentOrg,
    db: DbSession,
    include_superseded: bool = Query(default=False),
) -> list[MemoryRead]:
    rows = await knowledge.list_memories(
        db, org.id, include_superseded=include_superseded
    )
    return [MemoryRead.model_validate(m) for m in rows]


@router.post("/memory", response_model=MemoryRead, status_code=201)
async def create_memory(
    payload: MemoryCreate, org: CurrentOrg, user: CurrentUser, db: DbSession
) -> MemoryRead:
    """Record a company fact.

    A fact typed by a person is user-confirmed, so the user id is attached
    whenever that is the claimed provenance.
    """
    try:
        memory = await knowledge.record_memory(
            db,
            organization_id=org.id,
            key=payload.key,
            value=payload.value,
            category=payload.category,
            source_kind=payload.source_kind,
            confirmed_by_user_id=(
                user.id if payload.source_kind is FactSource.USER_CONFIRMED else None
            ),
        )
    except knowledge.KnowledgeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return MemoryRead.model_validate(memory)


@router.post("/memory/{memory_id}/confirm", response_model=MemoryRead)
async def confirm_memory(
    memory_id: uuid.UUID, org: CurrentOrg, user: CurrentUser, db: DbSession
) -> MemoryRead:
    """Promote an inferred fact to confirmed. Only a person can do this."""
    memory = await knowledge.get_memory(db, memory_id, org.id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryRead.model_validate(await knowledge.confirm_memory(db, memory, user.id))


@router.patch("/memory/{memory_id}", response_model=MemoryRead)
async def correct_memory(
    memory_id: uuid.UUID,
    payload: MemoryCorrect,
    org: CurrentOrg,
    user: CurrentUser,
    db: DbSession,
) -> MemoryRead:
    """Correct a fact. The old value is superseded, not erased."""
    memory = await knowledge.get_memory(db, memory_id, org.id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    corrected = await knowledge.correct_memory(
        db, memory, value=payload.value, user_id=user.id
    )
    return MemoryRead.model_validate(corrected)


@router.delete("/memory/{memory_id}", status_code=204)
async def delete_memory(memory_id: uuid.UUID, org: CurrentOrg, db: DbSession) -> None:
    memory = await knowledge.get_memory(db, memory_id, org.id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    await knowledge.delete_memory(db, memory)


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


@router.get("/knowledge/search", response_model=KnowledgeSearchRead)
async def search(
    org: CurrentOrg,
    db: DbSession,
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=10, ge=1, le=25),
) -> KnowledgeSearchRead:
    """What the board would retrieve for this question."""
    items = await knowledge.search_knowledge(db, org.id, q, limit=limit)
    verified = sum(1 for i in items if i.is_verified)
    return KnowledgeSearchRead(
        query=q,
        hits=[
            KnowledgeHitRead(
                source=i.source,
                excerpt=i.excerpt,
                provenance=i.provenance,
                provenance_label=knowledge.provenance_label(i.provenance),
                is_verified=i.is_verified,
                rank=i.rank,
            )
            for i in items
        ],
        verified_count=verified,
        note=(
            "Nothing matched. A meeting on this question would get no company "
            "records at all."
            if not items
            else f"{len(items)} item(s), {verified} verified."
        ),
    )
