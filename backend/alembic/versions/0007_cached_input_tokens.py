"""record cached input tokens

Revision ID: 0007_cached_tokens
Revises: 0006_token_usage
Create Date: 2026-10-26

The provider reports how much of each prompt it served from its own cache,
and cached input is billed at a fraction of fresh input. Ghost Board was
discarding that number, so its cost figures were a ceiling rather than a
cost. There is nothing to backfill: the counts were never captured, and
writing zeroes would be indistinguishable from "no cache hits".
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_cached_tokens"
down_revision: str | None = "0006_token_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "llm_usage_records",
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "meetings",
        sa.Column("cached_input_tokens_used", sa.Integer(), nullable=False, server_default="0"),
    )
    # The default exists only so the ALTER can run against existing rows.
    op.alter_column("llm_usage_records", "cached_input_tokens", server_default=None)
    op.alter_column("meetings", "cached_input_tokens_used", server_default=None)


def downgrade() -> None:
    op.drop_column("meetings", "cached_input_tokens_used")
    op.drop_column("llm_usage_records", "cached_input_tokens")
