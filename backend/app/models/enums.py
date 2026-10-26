"""Enumerations shared across the domain models."""

from enum import StrEnum


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MeetingMode(StrEnum):
    QUICK_CONSULTATION = "quick_consultation"
    EXECUTIVE_MEETING = "executive_meeting"
    FULL_BOARD = "full_board"
    DEVILS_ADVOCATE = "devils_advocate"
    STRATEGY_WORKSHOP = "strategy_workshop"


class MeetingStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MeetingStage(StrEnum):
    INTAKE = "intake"
    AGENDA = "agenda"
    ASSESSMENTS = "assessments"
    PRESENTATION = "presentation"
    DEBATE = "debate"
    REVISIONS = "revisions"
    SYNTHESIS = "synthesis"
    PERSISTED = "persisted"


class ParticipantStatus(StrEnum):
    WAITING = "waiting"
    SPEAKING = "speaking"
    RESEARCHING = "researching"
    CHALLENGING = "challenging"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class ActionItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(StrEnum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FactSource(StrEnum):
    """Spec section 9: memory must distinguish how a fact came to be known."""

    USER_CONFIRMED = "user_confirmed"
    IMPORTED_EVIDENCE = "imported_evidence"
    MODEL_INTERPRETATION = "model_interpretation"
    HYPOTHESIS = "hypothesis"
    ESTIMATE = "estimate"
    HISTORICAL_DECISION = "historical_decision"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class ToolInvocationStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
