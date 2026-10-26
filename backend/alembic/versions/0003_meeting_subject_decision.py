"""link a meeting to the decision it is stress-testing

Revision ID: 0003_subject
Revises: 0002_consult_msgs
Create Date: 2026-10-25

Devil's Advocate mode needs something to attack. The subject is a prior
StrategicDecision, referenced here rather than copied into the question text
so the orchestrator can read the actual recommendation, its options, and the
dissent that was already recorded against it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_subject"
down_revision: str | None = "0002_consult_msgs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("subject_decision_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_meetings_subject_decision",
        "meetings",
        "strategic_decisions",
        ["subject_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_meetings_subject_decision_id", "meetings", ["subject_decision_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_meetings_subject_decision_id", table_name="meetings")
    op.drop_constraint("fk_meetings_subject_decision", "meetings", type_="foreignkey")
    op.drop_column("meetings", "subject_decision_id")
