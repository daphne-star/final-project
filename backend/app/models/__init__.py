"""ORM models.

Importing this package registers every table on ``Base.metadata``, which is what
Alembic autogenerate and the test fixtures rely on.
"""

from app.db.base import Base
from app.models.agent import AgentConfiguration
from app.models.consultation import Consultation, ConsultationMessage
from app.models.decision import ActionItem, DecisionPosition, StrategicDecision
from app.models.document import Document, DocumentChunk, EvidenceSource
from app.models.identity import CompanyProfile, Organization, OrganizationMember, User
from app.models.meeting import (
    AgentAssessment,
    AgentObjection,
    AgentRevision,
    Meeting,
    MeetingEvent,
    MeetingParticipant,
    ToolInvocation,
)
from app.models.memory import CompanyMemory
from app.models.usage import LLMUsageRecord

__all__ = [
    "ActionItem",
    "AgentAssessment",
    "AgentConfiguration",
    "AgentObjection",
    "AgentRevision",
    "Base",
    "CompanyMemory",
    "CompanyProfile",
    "Consultation",
    "ConsultationMessage",
    "DecisionPosition",
    "Document",
    "DocumentChunk",
    "EvidenceSource",
    "LLMUsageRecord",
    "Meeting",
    "MeetingEvent",
    "MeetingParticipant",
    "Organization",
    "OrganizationMember",
    "StrategicDecision",
    "ToolInvocation",
    "User",
]
