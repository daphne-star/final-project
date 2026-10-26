"""Document ingestion: validate, extract, chunk, index.

Uploaded files are untrusted input twice over — once as bytes that have to be
parsed, and once as text that will end up near a model. Both are handled here:

* **As bytes.** The declared content type is not believed; the magic number
  decides. Size is capped before anything is parsed, and extraction runs
  inside a thread so a malformed PDF cannot block the event loop.
* **As text.** Extracted content is stored as evidence with its provenance,
  never as instructions. Agents receive it wrapped and labelled, and the
  house rules tell them content inside a document is data (spec section 8).
"""

from __future__ import annotations

import asyncio
import codecs
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.models.enums import DocumentStatus

logger = logging.getLogger(__name__)

#: Only these are accepted. Each is matched against its magic number too.
SUPPORTED_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "txt",
}

#: First bytes that must be present for a declared type to be believed.
MAGIC: dict[str, bytes] = {
    "pdf": b"%PDF-",
    # DOCX is a zip container.
    "docx": b"PK\x03\x04",
}

#: Roughly 900 words, which keeps a chunk inside any model's attention while
#: staying large enough to carry an argument rather than a fragment.
CHUNK_CHARS = 4000
CHUNK_OVERLAP = 400

class IngestionError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(slots=True)
class ExtractionResult:
    text: str
    page_count: int | None


def storage_dir() -> Path:
    """Where uploads live. Outside the package so a file cannot be imported."""
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_upload(filename: str, content_type: str, data: bytes) -> str:
    """Return the internal kind, or raise. Checks type, size, and magic bytes."""
    if not data:
        raise IngestionError("The file is empty.", code="empty_file")

    if len(data) > settings.max_upload_bytes:
        mb = settings.max_upload_bytes / 1_048_576
        raise IngestionError(
            f"File is larger than the {mb:.0f} MB limit.",
            code="file_too_large",
            status_code=413,
        )

    kind = SUPPORTED_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if kind is None:
        # Fall back to the extension; browsers are inconsistent about .md.
        suffix = Path(filename).suffix.lower()
        kind = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "txt"}.get(suffix)

    if kind is None:
        raise IngestionError(
            "Only PDF, DOCX, and plain text files are supported.",
            code="unsupported_type",
            status_code=415,
        )

    expected = MAGIC.get(kind)
    if expected and not data.startswith(expected):
        # A .pdf that is not a PDF is either a mistake or an attempt.
        raise IngestionError(
            f"The file does not look like a {kind.upper()} despite its name or type.",
            code="content_type_mismatch",
        )

    return kind


def _extract_pdf(data: bytes) -> ExtractionResult:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        raise IngestionError(
            "The PDF is encrypted and cannot be read.", code="encrypted_pdf"
        )
    pages = [page.extract_text() or "" for page in reader.pages]
    return ExtractionResult(text="\n\n".join(pages), page_count=len(pages))


def _extract_docx(data: bytes) -> ExtractionResult:
    from io import BytesIO

    import docx

    document = docx.Document(BytesIO(data))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return ExtractionResult(text="\n".join(parts), page_count=None)


def _extract_txt(data: bytes) -> ExtractionResult:
    # UTF-16 is only attempted when a BOM says so. Tried speculatively it
    # "succeeds" on plenty of single-byte text and returns mojibake, which is
    # worse than failing: the document indexes as nonsense.
    if data[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        candidates = ("utf-16", "utf-8", "cp1252", "latin-1")
    else:
        candidates = ("utf-8", "cp1252", "latin-1")

    for encoding in candidates:
        try:
            return ExtractionResult(text=data.decode(encoding), page_count=None)
        except UnicodeDecodeError:
            continue
    raise IngestionError("Could not decode the text file.", code="undecodable")


def extract_text(kind: str, data: bytes) -> ExtractionResult:
    """Synchronous extraction. Call through ``asyncio.to_thread``."""
    try:
        if kind == "pdf":
            return _extract_pdf(data)
        if kind == "docx":
            return _extract_docx(data)
        return _extract_txt(data)
    except IngestionError:
        raise
    except Exception as exc:
        raise IngestionError(
            f"Could not read the {kind.upper()}: {type(exc).__name__}",
            code="extraction_failed",
        ) from exc


_WHITESPACE = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def chunk_text(text: str, *, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on paragraph boundaries where possible, with a little overlap.

    Overlap matters for retrieval: a fact stated at a chunk boundary would
    otherwise be split across two chunks and match neither well.
    """
    text = normalise(text)
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Prefer a paragraph break, then a sentence end, then a space.
            for sep in ("\n\n", ". ", "\n", " "):
                cut = text.rfind(sep, start + size // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


async def ingest_document(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    filename: str,
    content_type: str,
    data: bytes,
) -> Document:
    """Validate, store, extract, chunk, and index one upload.

    The Document row is created before extraction so a failure is visible as
    a FAILED document with a reason, rather than an upload that silently
    never appears.
    """
    kind = validate_upload(filename, content_type, data)

    safe_name = Path(filename).name[:200] or "upload"
    stored_as = storage_dir() / f"{uuid.uuid4()}-{safe_name}"

    document = Document(
        organization_id=organization_id,
        uploaded_by_user_id=user_id,
        filename=safe_name,
        content_type=content_type or kind,
        size_bytes=len(data),
        storage_path=str(stored_as),
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    await db.flush()

    try:
        stored_as.write_bytes(data)
        # Parsing an untrusted file is CPU-bound and can be slow; keep it off
        # the event loop so one bad PDF cannot stall the whole server.
        extraction = await asyncio.to_thread(extract_text, kind, data)
    except IngestionError as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)
        await db.flush()
        raise

    chunks = chunk_text(extraction.text)
    if not chunks:
        document.status = DocumentStatus.FAILED
        document.error_message = (
            "No text could be extracted. If this is a scanned document it needs "
            "OCR, which is not supported."
        )
        await db.flush()
        raise IngestionError(document.error_message, code="no_text")

    for ordinal, content in enumerate(chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                organization_id=organization_id,
                ordinal=ordinal,
                content=content,
                token_estimate=len(content) // 4,
                chunk_metadata={
                    "filename": safe_name,
                    "kind": kind,
                    "page_count": extraction.page_count,
                },
            )
        )

    document.status = DocumentStatus.INDEXED
    await db.flush()
    await db.refresh(document)
    logger.info(
        "Ingested %s (%s) as %d chunk(s) for org %s",
        safe_name,
        kind,
        len(chunks),
        organization_id,
    )
    return document


async def delete_document(db: AsyncSession, document: Document) -> None:
    """Soft-delete the record and remove the stored bytes.

    The row is kept so prior evidence citations still resolve to something,
    but the file itself goes — a founder deleting a document expects the
    contents gone, not just hidden.
    """
    from datetime import UTC, datetime

    path = Path(document.storage_path)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        logger.exception("Could not remove stored file for document %s", document.id)

    await db.execute(
        DocumentChunk.__table__.delete().where(DocumentChunk.document_id == document.id)
    )
    document.deleted_at = datetime.now(UTC)
    document.status = DocumentStatus.UPLOADED
    await db.flush()


async def list_documents(
    db: AsyncSession, organization_id: uuid.UUID
) -> list[tuple[Document, int]]:
    """Documents with their chunk counts, newest first."""
    rows = (
        await db.execute(
            select(Document, func.count(DocumentChunk.id))
            .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
            .where(
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .group_by(Document.id)
            .order_by(Document.created_at.desc())
        )
    ).all()
    return [(doc, count) for doc, count in rows]
