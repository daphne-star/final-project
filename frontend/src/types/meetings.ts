/** Mirrors backend/app/schemas/meeting.py and app/orchestration/events.py. */

import type { ConfidenceLevel, OpenQuestion, Priority, Severity } from './consultations'

export type MeetingStatus =
  | 'draft'
  | 'running'
  | 'paused'
  | 'completed'
  | 'cancelled'
  | 'failed'

export type MeetingStage =
  | 'intake'
  | 'agenda'
  | 'assessments'
  | 'presentation'
  | 'debate'
  | 'revisions'
  | 'synthesis'
  | 'persisted'

export type ParticipantStatus =
  | 'waiting'
  | 'speaking'
  | 'researching'
  | 'challenging'
  | 'completed'
  | 'skipped'

export type MeetingMode =
  | 'quick_consultation'
  | 'executive_meeting'
  | 'full_board'
  | 'devils_advocate'
  | 'strategy_workshop'

export interface Participant {
  agent_id: string
  selection_reason: string | null
  status: ParticipantStatus
  speaking_order: number | null
}

export interface SupportingArgument {
  point: string
  reasoning: string
}

export interface EvidenceReference {
  claim: string
  source: string
  is_verified: boolean
}

export interface Assessment {
  id: string
  agent_id: string
  round_number: number
  summary: string
  recommended_position: string
  supporting_arguments: SupportingArgument[]
  evidence_references: EvidenceReference[]
  assumptions: { statement: string; why_it_matters: string; how_to_validate: string | null }[]
  risks: { description: string; severity: Severity; likelihood: ConfidenceLevel }[]
  opportunities: { description: string; potential_impact: string }[]
  open_questions: OpenQuestion[]
  confidence_level: ConfidenceLevel
  created_at: string
}

export interface Objection {
  id: string
  source_agent_id: string
  target_agent_id: string
  round_number: number
  challenged_claim: string
  objection: string
  supporting_evidence: string[]
  severity: Severity
  proposed_resolution: string | null
  created_at: string
}

export interface Revision {
  id: string
  agent_id: string
  round_number: number
  original_position: string
  updated_position: string
  reason_for_change: string
  evidence_considered: string[]
  created_at: string
}

export interface StrategicOption {
  option_id: string
  title: string
  description: string
  benefits: string[]
  risks: string[]
  costs: string[]
  dependencies: string[]
  assumptions: string[]
  evaluation: string
}

export interface DecisionPosition {
  agent_id: string
  stance: string
  position_summary: string
  rationale: string | null
  is_dissent: boolean
}

export interface DecisionActionItem {
  id: string
  description: string
  suggested_owner: string | null
  priority: Priority
  dependencies: string[]
  status: string
}

export interface Decision {
  id: string
  meeting_id: string | null
  title: string
  problem_statement: string
  executive_summary: string
  strategic_options: StrategicOption[]
  recommended_option_id: string | null
  recommendation_rationale: string | null
  financial_implications: string | null
  operational_implications: string | null
  legal_considerations: string | null
  customer_implications: string | null
  competitive_implications: string | null
  dissenting_opinions: { agent_id: string; position: string; reasoning: string }[]
  unresolved_questions: OpenQuestion[]
  confidence_and_uncertainty: string | null
  action_plan: {
    first_30_days?: PlanItem[]
    days_30_to_60?: PlanItem[]
    days_60_to_90?: PlanItem[]
  } | null
  status: 'proposed' | 'accepted' | 'rejected' | 'deferred'
  decision_notes: string | null
  positions: DecisionPosition[]
  action_items: DecisionActionItem[]
  created_at: string
}

export interface PlanItem {
  description: string
  suggested_owner: string | null
  priority: Priority
  target_window: string | null
  dependencies: string[]
}

export interface AgendaItem {
  title: string
  question: string
  why_it_matters: string
}

export interface MeetingAgenda {
  reframed_question: string
  agenda_items: AgendaItem[]
  participants: { agent_id: string; reason: string }[]
  tensions_to_test: string[]
}

export interface Meeting {
  id: string
  organization_id: string
  title: string
  question: string
  mode: MeetingMode
  status: MeetingStatus
  stage: MeetingStage
  agenda: MeetingAgenda | null
  started_at: string | null
  completed_at: string | null
  failure_reason: string | null
  debate_rounds_used: number
  model_requests_used: number
  input_tokens_used: number
  output_tokens_used: number
  total_tokens_used: number
  estimated_cost_usd: number
  created_at: string
}

export interface MeetingDetail extends Meeting {
  interventions: Intervention[]
  participants: Participant[]
  assessments: Assessment[]
  objections: Objection[]
  revisions: Revision[]
  decision: Decision | null
}

/** Event types emitted by the orchestrator. */
export type MeetingEventType =
  | 'meeting_started'
  | 'agenda_created'
  | 'stage_changed'
  | 'agent_started'
  | 'agent_status_changed'
  | 'agent_message_delta'
  | 'agent_message_completed'
  | 'objection_raised'
  | 'position_revised'
  | 'agent_failed'
  | 'user_intervention_requested'
  | 'intervention_answered'
  | 'meeting_paused'
  | 'meeting_resumed'
  | 'decision_generated'
  | 'meeting_completed'
  | 'meeting_cancelled'
  | 'meeting_failed'
  // Transport-level frames, not orchestrator events.
  | 'stream_closed'
  | 'stream_error'
  | 'stream_timeout'

export interface MeetingEvent {
  event_id: string
  meeting_id: string
  sequence_number: number
  event_type: MeetingEventType
  agent_id: string | null
  payload: Record<string, unknown>
  timestamp: string
}


export type InterventionKind =
  | 'ask'
  | 'challenge'
  | 'request_evidence'
  | 'critique_colleague'
  | 'request_alternative'
  | 'implementation_detail'
  | 'explain_risk'

export type InterventionStatus =
  | 'queued'
  | 'running'
  | 'answered'
  | 'failed'
  | 'abandoned'

export interface Intervention {
  id: string
  agent_id: string
  about_agent_id: string | null
  kind: InterventionKind
  prompt: string
  status: InterventionStatus
  answered_at_stage: string | null
  response: string | null
  structured_response: Record<string, unknown> | null
  error_message: string | null
  answered_at: string | null
  duration_ms: number | null
  created_at: string
}

export interface ActionItemDetail {
  id: string
  decision_id: string | null
  description: string
  suggested_owner: string | null
  priority: Priority
  dependencies: string[]
  status: 'open' | 'in_progress' | 'blocked' | 'done' | 'cancelled'
  target_date: string | null
  outcome_notes: string | null
  created_at: string
}
