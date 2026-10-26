"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-25

Generated from app.models metadata. Verify against a live database with
`alembic check` once Postgres is available.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    postgresql.ENUM('OPEN', 'IN_PROGRESS', 'BLOCKED', 'DONE', 'CANCELLED', name='action_item_status').create(bind, checkfirst=True)
    postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='action_priority').create(bind, checkfirst=True)
    postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', name='confidence_level').create(bind, checkfirst=True)
    postgresql.ENUM('DRAFT', 'RUNNING', 'PAUSED', 'COMPLETED', 'CANCELLED', 'FAILED', name='consultation_status').create(bind, checkfirst=True)
    postgresql.ENUM('PROPOSED', 'ACCEPTED', 'REJECTED', 'DEFERRED', name='decision_status').create(bind, checkfirst=True)
    postgresql.ENUM('UPLOADED', 'PROCESSING', 'INDEXED', 'FAILED', name='document_status').create(bind, checkfirst=True)
    postgresql.ENUM('USER_CONFIRMED', 'IMPORTED_EVIDENCE', 'MODEL_INTERPRETATION', 'HYPOTHESIS', 'ESTIMATE', 'HISTORICAL_DECISION', name='fact_source').create(bind, checkfirst=True)
    postgresql.ENUM('QUICK_CONSULTATION', 'EXECUTIVE_MEETING', 'FULL_BOARD', 'DEVILS_ADVOCATE', 'STRATEGY_WORKSHOP', name='meeting_mode').create(bind, checkfirst=True)
    postgresql.ENUM('INTAKE', 'AGENDA', 'ASSESSMENTS', 'PRESENTATION', 'DEBATE', 'REVISIONS', 'SYNTHESIS', 'PERSISTED', name='meeting_stage').create(bind, checkfirst=True)
    postgresql.ENUM('DRAFT', 'RUNNING', 'PAUSED', 'COMPLETED', 'CANCELLED', 'FAILED', name='meeting_status').create(bind, checkfirst=True)
    postgresql.ENUM('MINOR', 'MODERATE', 'MAJOR', 'CRITICAL', name='objection_severity').create(bind, checkfirst=True)
    postgresql.ENUM('OWNER', 'ADMIN', 'MEMBER', name='org_role').create(bind, checkfirst=True)
    postgresql.ENUM('WAITING', 'SPEAKING', 'RESEARCHING', 'CHALLENGING', 'COMPLETED', 'SKIPPED', name='participant_status').create(bind, checkfirst=True)
    postgresql.ENUM('STARTED', 'SUCCEEDED', 'FAILED', 'DENIED', name='tool_invocation_status').create(bind, checkfirst=True)

    op.create_table('organizations',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=200), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('agent_configurations',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=True),
    sa.Column('temperature', sa.Float(), nullable=True),
    sa.Column('max_tokens', sa.Integer(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'agent_id', name='uq_org_agent')
    )
    op.create_table('company_profiles',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('company_name', sa.String(length=200), nullable=False),
    sa.Column('industry', sa.String(length=200), nullable=True),
    sa.Column('business_model', sa.Text(), nullable=True),
    sa.Column('stage', sa.String(length=100), nullable=True),
    sa.Column('headcount', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('products', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('customer_segments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('goals', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('challenges', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('constraints', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('arr_usd', sa.Double(), nullable=True),
    sa.Column('monthly_burn_usd', sa.Double(), nullable=True),
    sa.Column('cash_on_hand_usd', sa.Double(), nullable=True),
    sa.Column('runway_months', sa.Double(), nullable=True),
    sa.Column('annual_churn_rate', sa.Double(), nullable=True),
    sa.Column('revenue_model', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id')
    )
    op.create_table('consultations',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('status', postgresql.ENUM('DRAFT', 'RUNNING', 'PAUSED', 'COMPLETED', 'CANCELLED', 'FAILED', name='consultation_status', create_type=False), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('documents',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('uploaded_by_user_id', sa.UUID(), nullable=True),
    sa.Column('filename', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=128), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(length=1000), nullable=False),
    sa.Column('status', postgresql.ENUM('UPLOADED', 'PROCESSING', 'INDEXED', 'FAILED', name='document_status', create_type=False), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('meetings',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('mode', postgresql.ENUM('QUICK_CONSULTATION', 'EXECUTIVE_MEETING', 'FULL_BOARD', 'DEVILS_ADVOCATE', 'STRATEGY_WORKSHOP', name='meeting_mode', create_type=False), nullable=False),
    sa.Column('status', postgresql.ENUM('DRAFT', 'RUNNING', 'PAUSED', 'COMPLETED', 'CANCELLED', 'FAILED', name='meeting_status', create_type=False), nullable=False),
    sa.Column('stage', postgresql.ENUM('INTAKE', 'AGENDA', 'ASSESSMENTS', 'PRESENTATION', 'DEBATE', 'REVISIONS', 'SYNTHESIS', 'PERSISTED', name='meeting_stage', create_type=False), nullable=False),
    sa.Column('agenda', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('debate_rounds_used', sa.Integer(), nullable=False),
    sa.Column('model_requests_used', sa.Integer(), nullable=False),
    sa.Column('tool_calls_used', sa.Integer(), nullable=False),
    sa.Column('estimated_cost_usd', sa.Float(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('organization_members',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', postgresql.ENUM('OWNER', 'ADMIN', 'MEMBER', name='org_role', create_type=False), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member')
    )
    op.create_table('agent_assessments',
    sa.Column('meeting_id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('round_number', sa.Integer(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('recommended_position', sa.Text(), nullable=False),
    sa.Column('supporting_arguments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('evidence_references', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('assumptions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('risks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('opportunities', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('open_questions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('confidence_level', postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', name='confidence_level', create_type=False), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('agent_objections',
    sa.Column('meeting_id', sa.UUID(), nullable=False),
    sa.Column('source_agent_id', sa.String(length=64), nullable=False),
    sa.Column('target_agent_id', sa.String(length=64), nullable=False),
    sa.Column('round_number', sa.Integer(), nullable=False),
    sa.Column('challenged_claim', sa.Text(), nullable=False),
    sa.Column('objection', sa.Text(), nullable=False),
    sa.Column('supporting_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('severity', postgresql.ENUM('MINOR', 'MODERATE', 'MAJOR', 'CRITICAL', name='objection_severity', create_type=False), nullable=False),
    sa.Column('proposed_resolution', sa.Text(), nullable=True),
    sa.Column('resolved', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('agent_revisions',
    sa.Column('meeting_id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('round_number', sa.Integer(), nullable=False),
    sa.Column('original_position', sa.Text(), nullable=False),
    sa.Column('updated_position', sa.Text(), nullable=False),
    sa.Column('reason_for_change', sa.Text(), nullable=False),
    sa.Column('evidence_considered', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('company_memories',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=200), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('source_kind', postgresql.ENUM('USER_CONFIRMED', 'IMPORTED_EVIDENCE', 'MODEL_INTERPRETATION', 'HYPOTHESIS', 'ESTIMATE', 'HISTORICAL_DECISION', name='fact_source', create_type=False), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('confirmed_by_user_id', sa.UUID(), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('superseded', sa.Boolean(), nullable=False),
    sa.Column('origin_meeting_id', sa.UUID(), nullable=True),
    sa.Column('origin_document_id', sa.UUID(), nullable=True),
    sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['confirmed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['origin_document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['origin_meeting_id'], ['meetings.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('consultation_messages',
    sa.Column('consultation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('structured_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('promoted_to_meeting', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('document_chunks',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('token_estimate', sa.Integer(), nullable=True),
    sa.Column('chunk_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('llm_usage_records',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('meeting_id', sa.UUID(), nullable=True),
    sa.Column('consultation_id', sa.UUID(), nullable=True),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=False),
    sa.Column('stage', sa.String(length=64), nullable=True),
    sa.Column('request_count', sa.Integer(), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('total_tokens', sa.Integer(), nullable=False),
    sa.Column('estimated_cost_usd', sa.Float(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('meeting_events',
    sa.Column('meeting_id', sa.UUID(), nullable=False),
    sa.Column('sequence_number', sa.BigInteger(), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('meeting_id', 'sequence_number', name='uq_meeting_event_seq')
    )
    op.create_table('meeting_participants',
    sa.Column('meeting_id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('selection_reason', sa.Text(), nullable=True),
    sa.Column('status', postgresql.ENUM('WAITING', 'SPEAKING', 'RESEARCHING', 'CHALLENGING', 'COMPLETED', 'SKIPPED', name='participant_status', create_type=False), nullable=False),
    sa.Column('speaking_order', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('meeting_id', 'agent_id', name='uq_meeting_agent')
    )
    op.create_table('strategic_decisions',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('meeting_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('problem_statement', sa.Text(), nullable=False),
    sa.Column('executive_summary', sa.Text(), nullable=False),
    sa.Column('strategic_options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('recommended_option_id', sa.String(length=64), nullable=True),
    sa.Column('recommendation_rationale', sa.Text(), nullable=True),
    sa.Column('financial_implications', sa.Text(), nullable=True),
    sa.Column('operational_implications', sa.Text(), nullable=True),
    sa.Column('legal_considerations', sa.Text(), nullable=True),
    sa.Column('customer_implications', sa.Text(), nullable=True),
    sa.Column('competitive_implications', sa.Text(), nullable=True),
    sa.Column('dissenting_opinions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('unresolved_questions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('confidence_and_uncertainty', sa.Text(), nullable=True),
    sa.Column('action_plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', postgresql.ENUM('PROPOSED', 'ACCEPTED', 'REJECTED', 'DEFERRED', name='decision_status', create_type=False), nullable=False),
    sa.Column('decided_by_user_id', sa.UUID(), nullable=True),
    sa.Column('decision_notes', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['decided_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tool_invocations',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('meeting_id', sa.UUID(), nullable=True),
    sa.Column('consultation_id', sa.UUID(), nullable=True),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('tool_name', sa.String(length=128), nullable=False),
    sa.Column('arguments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', postgresql.ENUM('STARTED', 'SUCCEEDED', 'FAILED', 'DENIED', name='tool_invocation_status', create_type=False), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('action_items',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('decision_id', sa.UUID(), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('suggested_owner', sa.String(length=200), nullable=True),
    sa.Column('assigned_user_id', sa.UUID(), nullable=True),
    sa.Column('priority', postgresql.ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='action_priority', create_type=False), nullable=False),
    sa.Column('target_date', sa.Date(), nullable=True),
    sa.Column('dependencies', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', postgresql.ENUM('OPEN', 'IN_PROGRESS', 'BLOCKED', 'DONE', 'CANCELLED', name='action_item_status', create_type=False), nullable=False),
    sa.Column('outcome_notes', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['decision_id'], ['strategic_decisions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('decision_positions',
    sa.Column('decision_id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('stance', sa.String(length=32), nullable=False),
    sa.Column('position_summary', sa.Text(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=True),
    sa.Column('is_dissent', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['decision_id'], ['strategic_decisions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('evidence_sources',
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('meeting_id', sa.UUID(), nullable=True),
    sa.Column('document_chunk_id', sa.UUID(), nullable=True),
    sa.Column('tool_invocation_id', sa.UUID(), nullable=True),
    sa.Column('label', sa.String(length=300), nullable=False),
    sa.Column('excerpt', sa.Text(), nullable=True),
    sa.Column('url', sa.String(length=2000), nullable=True),
    sa.Column('source_kind', postgresql.ENUM('USER_CONFIRMED', 'IMPORTED_EVIDENCE', 'MODEL_INTERPRETATION', 'HYPOTHESIS', 'ESTIMATE', 'HISTORICAL_DECISION', name='fact_source', create_type=False), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_chunk_id'], ['document_chunks.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tool_invocation_id'], ['tool_invocations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_index(op.f('ix_organizations_deleted_at'), 'organizations', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)
    op.create_index(op.f('ix_users_deleted_at'), 'users', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_agent_configurations_agent_id'), 'agent_configurations', ['agent_id'], unique=False)
    op.create_index('ix_consultation_org_agent', 'consultations', ['organization_id', 'agent_id'], unique=False)
    op.create_index('ix_document_org_created', 'documents', ['organization_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_documents_deleted_at'), 'documents', ['deleted_at'], unique=False)
    op.create_index('ix_meetings_org_created', 'meetings', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_org_member_user', 'organization_members', ['user_id'], unique=False)
    op.create_index('ix_assessment_meeting_agent', 'agent_assessments', ['meeting_id', 'agent_id'], unique=False)
    op.create_index('ix_objection_meeting', 'agent_objections', ['meeting_id'], unique=False)
    op.create_index('ix_revision_meeting_agent', 'agent_revisions', ['meeting_id', 'agent_id'], unique=False)
    op.create_index(op.f('ix_company_memories_deleted_at'), 'company_memories', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_company_memories_key'), 'company_memories', ['key'], unique=False)
    op.create_index('ix_memory_org_kind', 'company_memories', ['organization_id', 'source_kind'], unique=False)
    op.create_index('ix_memory_search', 'company_memories', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('ix_consultation_message_parent', 'consultation_messages', ['consultation_id', 'created_at'], unique=False)
    op.create_index('ix_chunk_document_ordinal', 'document_chunks', ['document_id', 'ordinal'], unique=False)
    op.create_index('ix_chunk_search', 'document_chunks', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_llm_usage_records_agent_id'), 'llm_usage_records', ['agent_id'], unique=False)
    op.create_index('ix_usage_meeting', 'llm_usage_records', ['meeting_id'], unique=False)
    op.create_index('ix_usage_org_created', 'llm_usage_records', ['organization_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_meeting_events_event_type'), 'meeting_events', ['event_type'], unique=False)
    op.create_index('ix_meeting_events_meeting_seq', 'meeting_events', ['meeting_id', 'sequence_number'], unique=False)
    op.create_index(op.f('ix_meeting_events_timestamp'), 'meeting_events', ['timestamp'], unique=False)
    op.create_index('ix_decision_org_status', 'strategic_decisions', ['organization_id', 'status'], unique=False)
    op.create_index('ix_tool_invocation_org_created', 'tool_invocations', ['organization_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_tool_invocations_tool_name'), 'tool_invocations', ['tool_name'], unique=False)
    op.create_index('ix_action_org_status', 'action_items', ['organization_id', 'status'], unique=False)
    op.create_index('ix_position_decision_agent', 'decision_positions', ['decision_id', 'agent_id'], unique=False)
    op.create_index('ix_evidence_org_meeting', 'evidence_sources', ['organization_id', 'meeting_id'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table('evidence_sources')
    op.drop_table('decision_positions')
    op.drop_table('action_items')
    op.drop_table('tool_invocations')
    op.drop_table('strategic_decisions')
    op.drop_table('meeting_participants')
    op.drop_table('meeting_events')
    op.drop_table('llm_usage_records')
    op.drop_table('document_chunks')
    op.drop_table('consultation_messages')
    op.drop_table('company_memories')
    op.drop_table('agent_revisions')
    op.drop_table('agent_objections')
    op.drop_table('agent_assessments')
    op.drop_table('organization_members')
    op.drop_table('meetings')
    op.drop_table('documents')
    op.drop_table('consultations')
    op.drop_table('company_profiles')
    op.drop_table('agent_configurations')
    op.drop_table('users')
    op.drop_table('organizations')

    postgresql.ENUM(name='action_item_status').drop(bind, checkfirst=True)
    postgresql.ENUM(name='action_priority').drop(bind, checkfirst=True)
    postgresql.ENUM(name='confidence_level').drop(bind, checkfirst=True)
    postgresql.ENUM(name='consultation_status').drop(bind, checkfirst=True)
    postgresql.ENUM(name='decision_status').drop(bind, checkfirst=True)
    postgresql.ENUM(name='document_status').drop(bind, checkfirst=True)
    postgresql.ENUM(name='fact_source').drop(bind, checkfirst=True)
    postgresql.ENUM(name='meeting_mode').drop(bind, checkfirst=True)
    postgresql.ENUM(name='meeting_stage').drop(bind, checkfirst=True)
    postgresql.ENUM(name='meeting_status').drop(bind, checkfirst=True)
    postgresql.ENUM(name='objection_severity').drop(bind, checkfirst=True)
    postgresql.ENUM(name='org_role').drop(bind, checkfirst=True)
    postgresql.ENUM(name='participant_status').drop(bind, checkfirst=True)
    postgresql.ENUM(name='tool_invocation_status').drop(bind, checkfirst=True)
