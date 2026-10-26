/** Mirrors `ExecutiveDefinition` in backend/app/agents/registry.py. */
export interface ExecutiveDefinition {
  agent_id: string
  display_name: string
  title: string
  short_title: string
  expertise_descriptor: string
  role_summary: string
  responsibilities: string[]
  distinctive_perspective: string
  personality: string
  tool_scopes: string[]
  can_chair: boolean
  can_consult_one_on_one: boolean
  theme_color: string
  theme_color_soft: string
  symbol: string
  avatar_ref: string
}

/**
 * Card states. Everything past `idle` is driven by real backend meeting
 * events in later phases — nothing here is on a timer.
 */
export type ExecutiveStatus =
  | 'idle'
  | 'waiting'
  | 'speaking'
  | 'researching'
  | 'challenging'
  | 'completed'
  | 'skipped'

export interface HealthResponse {
  status: string
  app: string
  environment: string
  database: string
  version: string
}
