"""record token usage on the meeting

Revision ID: 0006_token_usage
Revises: 0005_interventions
Create Date: 2026-10-26

Per-call token counts already lived on llm_usage_records. What was missing
was a per-meeting total, so reopening a finished meeting had nothing to show
but a model-request count -- a number that says how many times the board was
asked something, not how much work it did.

Existing rows backfill from llm_usage_records rather than defaulting to zero,
which would have claimed every past meeting cost nothing.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_token_usage"
down_revision: str | None = "0005_interventions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("input_tokens_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "meetings",
        sa.Column("output_tokens_used", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        """
        UPDATE meetings m
        SET input_tokens_used = totals.input_tokens,
            output_tokens_used = totals.output_tokens
        FROM (
            SELECT meeting_id,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens
            FROM llm_usage_records
            WHERE meeting_id IS NOT NULL
            GROUP BY meeting_id
        ) AS totals
        WHERE totals.meeting_id = m.id
        """
    )

    # The default existed only to backfill; new rows get theirs from the ORM.
    op.alter_column("meetings", "input_tokens_used", server_default=None)
    op.alter_column("meetings", "output_tokens_used", server_default=None)


def downgrade() -> None:
    op.drop_column("meetings", "output_tokens_used")
    op.drop_column("meetings", "input_tokens_used")
