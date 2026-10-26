"""store pydantic-ai message history on consultation messages

Revision ID: 0002_consult_msgs
Revises: 0001_initial
Create Date: 2026-10-25

Multi-turn consultations replay prior turns through Pydantic AI, which needs
the real ModelMessage objects rather than a reconstruction from plain text.
Reconstructing would silently drop tool calls once Phase 5 lands, so the
serialized history is persisted alongside the human-readable content.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_consult_msgs"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consultation_messages",
        sa.Column("model_messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consultation_messages", "model_messages")
