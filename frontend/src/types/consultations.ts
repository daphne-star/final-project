/** Mirrors backend/app/agents/schemas.py and app/schemas/consultation.py. */

export type ConfidenceLevel = 'low' | 'medium' | 'high'
export type Severity = 'minor' | 'moderate' | 'major' | 'critical'
export type Priority = 'low' | 'medium' | 'high' | 'critical'

export interface Assumption {
  statement: string
  why_it_matters: string
  how_to_validate: string | null
}

export interface Risk {
  description: string
  severity: Severity
  likelihood: ConfidenceLevel
  mitigation: string | null
}

export interface OpenQuestion {
  question: string
  why_it_matters: string
  who_should_answer: string | null
}

export interface RecommendedAction {
  description: string
  priority: Priority
  suggested_owner: string | null
  rough_timeline: string | null
}

export interface ConsultationStructured {
  answer: string
  key_points: string[]
  assumptions: Assumption[]
  risks: Risk[]
  open_questions: OpenQuestion[]
  recommended_actions: RecommendedAction[]
  confidence_level: ConfidenceLevel
  out_of_scope: boolean
  refer_to_agent_id: string | null
}

export interface ConsultationMessage {
  id: string
  role: 'user' | 'agent' | 'system'
  agent_id: string | null
  content: string
  structured_output: ConsultationStructured | null
  created_at: string
}

export interface Consultation {
  id: string
  organization_id: string
  agent_id: string
  title: string
  status: string
  created_at: string
  updated_at: string
}

export interface ConsultationDetail extends Consultation {
  messages: ConsultationMessage[]
}

export interface ConsultationSummary extends Consultation {
  message_count: number
  last_message_at: string | null
}

export interface TurnResponse {
  user_message: ConsultationMessage
  agent_message: ConsultationMessage
  structured: ConsultationStructured
}

export interface MeResponse {
  user: { id: string; email: string; full_name: string | null }
  organizations: { organization: { id: string; name: string }; role: string }[]
  active_organization_id: string | null
}
