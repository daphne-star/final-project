"""user interventions in live meetings

Revision ID: 0005_interventions
Revises: 0004_tsvector
Create Date: 2026-10-25

Interventions are a persisted queue rather than a frontend state change:
the API writes a row, the running meeting drains it at a safe point, and
the exchange stays in the meeting's history.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '0005_interventions'
down_revision: str | None = '0004_tsvector'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('meeting_interventions',
    sa.Column('meeting_id', sa.UUID(), nullable=False),
    sa.Column('requested_by_user_id', sa.UUID(), nullable=True),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('about_agent_id', sa.String(length=64), nullable=True),
    sa.Column('kind', sa.Enum('ASK', 'CHALLENGE', 'REQUEST_EVIDENCE', 'CRITIQUE_COLLEAGUE', 'REQUEST_ALTERNATIVE', 'IMPLEMENTATION_DETAIL', 'EXPLAIN_RISK', name='intervention_kind'), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('QUEUED', 'RUNNING', 'ANSWERED', 'FAILED', 'ABANDONED', name='intervention_status'), nullable=False),
    sa.Column('answered_at_stage', sa.String(length=64), nullable=True),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('structured_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_intervention_meeting_created', 'meeting_interventions', ['meeting_id', 'created_at'], unique=False)
    op.create_index('ix_intervention_meeting_status', 'meeting_interventions', ['meeting_id', 'status'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index('ix_intervention_meeting_status', table_name='meeting_interventions')
    op.drop_index('ix_intervention_meeting_created', table_name='meeting_interventions')
    op.drop_table('meeting_interventions')
    # Autogenerate does not drop the enum types it created, which
    # makes a downgrade/upgrade cycle fail on 'type already exists'.
    postgresql.ENUM(name="intervention_kind").drop(bind, checkfirst=True)
    postgresql.ENUM(name="intervention_status").drop(bind, checkfirst=True)
