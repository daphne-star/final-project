/**
 * Derives everything the boardroom renders from the ordered event log.
 *
 * Kept as a pure reducer with no React or network in it, so the UI has one
 * source of truth whether events arrive live over SSE or are replayed from
 * the database on a refresh — and so it can be tested against fixture events
 * without a server.
 */

import type {
  AgendaItem,
  MeetingEvent,
  MeetingStage,
  MeetingStatus,
  ParticipantStatus,
} from '@/types/meetings'

/** What an executive is doing right now, as reported by the backend. */
export type AgentActivity =
  | 'waiting'
  | 'analyzing'
  | 'speaking'
  | 'challenging'
  | 'revising'
  | 'finished'
  | 'failed'
  | 'skipped'

export type TranscriptKind =
  | 'agenda'
  | 'assessment'
  | 'objection'
  | 'revision'
  | 'decision'
  | 'failure'
  | 'intervention'
  | 'intervention_answer'

export interface TranscriptEntry {
  id: string
  sequence: number
  kind: TranscriptKind
  agentId: string
  /** Set for objections: who is being challenged. */
  targetAgentId?: string
  timestamp: string
  title: string
  body: string
  meta?: Record<string, string | number | boolean | null | undefined>
}

export interface BoardroomState {
  status: MeetingStatus | null
  stage: MeetingStage | null
  /** agent_id -> what they are doing. Only backend events move these. */
  activity: Record<string, AgentActivity>
  participants: string[]
  reframedQuestion: string | null
  agendaItems: AgendaItem[]
  tensions: string[]
  transcript: TranscriptEntry[]
  /** Claims under dispute, for the right-hand panel. */
  disagreements: {
    id: string
    challenger: string
    target: string
    claim: string
    severity: string
    stance: string
  }[]
  evidence: { id: string; agentId: string; text: string }[]
  emergingPositions: Record<string, string>
  paused: boolean
  decisionGenerated: boolean
  recommendedOptionId: string | null
  failureReason: string | null
  lastSequence: number
  modelRequests: number | null
  /** Running total, updated at each stage boundary and finalised on completion. */
  totalTokens: number | null
}

export function initialBoardroomState(): BoardroomState {
  return {
    status: null,
    stage: null,
    activity: {},
    participants: [],
    reframedQuestion: null,
    agendaItems: [],
    tensions: [],
    transcript: [],
    disagreements: [],
    evidence: [],
    emergingPositions: {},
    paused: false,
    decisionGenerated: false,
    recommendedOptionId: null,
    failureReason: null,
    lastSequence: 0,
    modelRequests: null,
    totalTokens: null,
  }
}

/** Backend participant status -> the vocabulary the UI shows. */
const STATUS_TO_ACTIVITY: Record<ParticipantStatus, AgentActivity> = {
  waiting: 'waiting',
  speaking: 'speaking',
  researching: 'analyzing',
  challenging: 'challenging',
  completed: 'finished',
  skipped: 'skipped',
}

/** Stage an agent was started for -> what to show while it runs. */
const STAGE_TO_ACTIVITY: Record<string, AgentActivity> = {
  agenda: 'analyzing',
  assessment: 'analyzing',
  debate_plan: 'analyzing',
  objection: 'challenging',
  revision: 'revising',
  synthesis: 'speaking',
}

function str(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

export function reduceEvent(state: BoardroomState, event: MeetingEvent): BoardroomState {
  // Events are ordered and gapless; anything at or before the cursor is a
  // replay of something already applied.
  if (event.sequence_number <= state.lastSequence) return state

  const next: BoardroomState = {
    ...state,
    lastSequence: event.sequence_number,
    activity: { ...state.activity },
    emergingPositions: { ...state.emergingPositions },
  }
  const p = event.payload
  const agentId = event.agent_id ?? ''

  switch (event.event_type) {
    case 'meeting_started':
      next.status = 'running'
      break

    case 'stage_changed':
      next.stage = str(p.stage) as MeetingStage
      // The orchestrator attaches the running token total here rather than
      // emitting a counter event of its own.
      if (p.total_tokens != null) next.totalTokens = Number(p.total_tokens)
      break

    case 'agenda_created': {
      next.reframedQuestion = str(p.reframed_question)
      next.agendaItems = (p.agenda_items as AgendaItem[]) ?? []
      next.tensions = (p.tensions_to_test as string[]) ?? []
      next.participants = (p.participants as string[]) ?? []
      for (const id of next.participants) {
        next.activity[id] = next.activity[id] ?? 'waiting'
      }
      next.activity[agentId] = 'finished'
      next.transcript = [
        ...state.transcript,
        {
          id: str(p.event_id, `agenda-${event.sequence_number}`),
          sequence: event.sequence_number,
          kind: 'agenda',
          agentId,
          timestamp: event.timestamp,
          title: 'Meeting agenda',
          body: str(p.reframed_question),
          meta: { items: next.agendaItems.length },
        },
      ]
      break
    }

    case 'agent_started': {
      const stage = str(p.stage)
      next.activity[agentId] = STAGE_TO_ACTIVITY[stage] ?? 'analyzing'
      break
    }

    case 'agent_status_changed': {
      const status = str(p.status) as ParticipantStatus
      const mapped = STATUS_TO_ACTIVITY[status]
      if (mapped) next.activity[agentId] = mapped
      break
    }

    case 'agent_message_completed': {
      const stage = str(p.stage)
      if (stage === 'assessment') {
        next.activity[agentId] = 'finished'
        next.emergingPositions[agentId] = str(p.recommended_position)
        next.transcript = [
          ...state.transcript,
          {
            id: `assessment-${event.sequence_number}`,
            sequence: event.sequence_number,
            kind: 'assessment',
            agentId,
            timestamp: event.timestamp,
            title: 'Independent assessment',
            body: str(p.summary),
            meta: {
              position: str(p.recommended_position),
              confidence: str(p.confidence_level),
            },
          },
        ]
      } else if (stage === 'debate_plan') {
        next.transcript = [
          ...state.transcript,
          {
            id: `debate-plan-${event.sequence_number}`,
            sequence: event.sequence_number,
            kind: 'agenda',
            agentId,
            timestamp: event.timestamp,
            title: p.conflicts_found ? 'Challenges assigned' : 'No conflicts found',
            body: str(p.rationale),
            meta: { assignments: Number(p.assignment_count ?? 0) },
          },
        ]
      }
      break
    }

    case 'objection_raised': {
      const target = str(p.target_agent_id)
      next.activity[agentId] = 'finished'
      next.disagreements = [
        ...state.disagreements,
        {
          id: `objection-${event.sequence_number}`,
          challenger: agentId,
          target,
          claim: str(p.challenged_claim),
          severity: str(p.severity),
          stance: str(p.stance),
        },
      ]
      next.transcript = [
        ...state.transcript,
        {
          id: `objection-${event.sequence_number}`,
          sequence: event.sequence_number,
          kind: 'objection',
          agentId,
          targetAgentId: target,
          timestamp: event.timestamp,
          title: 'Challenge',
          body: str(p.objection),
          meta: { claim: str(p.challenged_claim), severity: str(p.severity) },
        },
      ]
      break
    }

    case 'position_revised': {
      const changed = Boolean(p.position_changed)
      next.emergingPositions[agentId] = str(p.updated_position)
      next.transcript = [
        ...state.transcript,
        {
          id: `revision-${event.sequence_number}`,
          sequence: event.sequence_number,
          kind: 'revision',
          agentId,
          timestamp: event.timestamp,
          title: changed ? 'Revised position' : 'Held position',
          body: str(p.reason_for_change),
          meta: {
            changed,
            before: str(p.original_position),
            after: str(p.updated_position),
          },
        },
      ]
      break
    }

    case 'user_intervention_requested': {
      next.transcript = [
        ...state.transcript,
        {
          id: `intervention-${event.sequence_number}`,
          sequence: event.sequence_number,
          kind: 'intervention',
          agentId,
          targetAgentId: str(p.about_agent_id) || undefined,
          timestamp: event.timestamp,
          title: 'You asked',
          body: str(p.prompt),
          meta: { interventionKind: str(p.kind) },
        },
      ]
      break
    }

    case 'intervention_answered': {
      next.transcript = [
        ...state.transcript,
        {
          id: `intervention-answer-${event.sequence_number}`,
          sequence: event.sequence_number,
          kind: 'intervention_answer',
          agentId,
          timestamp: event.timestamp,
          title: 'Replied to you',
          body: str(p.answer),
          meta: { confidence: str(p.confidence_level) },
        },
      ]
      break
    }

    case 'meeting_paused':
      next.paused = true
      break

    case 'meeting_resumed':
      next.paused = false
      break

    case 'agent_failed': {
      next.activity[agentId] = 'failed'
      next.transcript = [
        ...state.transcript,
        {
          id: `failure-${event.sequence_number}`,
          sequence: event.sequence_number,
          kind: 'failure',
          agentId,
          timestamp: event.timestamp,
          title: 'Could not contribute',
          body: str(p.error),
          meta: { stage: str(p.stage) },
        },
      ]
      break
    }

    case 'decision_generated':
      next.decisionGenerated = true
      next.recommendedOptionId = str(p.recommended_option_id) || null
      next.transcript = [
        ...state.transcript,
        {
          id: `decision-${event.sequence_number}`,
          sequence: event.sequence_number,
          kind: 'decision',
          agentId,
          timestamp: event.timestamp,
          title: 'Decision brief',
          body: `Recommended: ${str(p.recommended_option_id)}`,
          meta: {
            options: Number(p.option_count ?? 0),
            dissent: Number(p.dissent_count ?? 0),
            confidence: str(p.confidence_level),
          },
        },
      ]
      break

    case 'meeting_completed':
      next.status = 'completed'
      next.paused = false
      next.modelRequests = Number(p.model_requests ?? 0)
      if (p.total_tokens != null) next.totalTokens = Number(p.total_tokens)
      for (const id of Object.keys(next.activity)) {
        if (next.activity[id] !== 'failed' && next.activity[id] !== 'skipped') {
          next.activity[id] = 'finished'
        }
      }
      break

    case 'meeting_failed':
      next.status = 'failed'
      next.failureReason = str(p.reason)
      break

    case 'meeting_cancelled':
      next.status = 'cancelled'
      break

    default:
      break
  }

  return next
}

export function reduceEvents(events: MeetingEvent[]): BoardroomState {
  return events.reduce(reduceEvent, initialBoardroomState())
}

/** Human label for an activity, used on cards and status chips. */
export const ACTIVITY_LABEL: Record<AgentActivity, string> = {
  waiting: 'Waiting',
  analyzing: 'Analyzing',
  speaking: 'Speaking',
  challenging: 'Challenging',
  revising: 'Revising',
  finished: 'Finished',
  failed: 'Failed',
  skipped: 'Not called',
}

/** Activities that mean the agent is actively working right now. */
export const ACTIVE_ACTIVITIES: ReadonlySet<AgentActivity> = new Set<AgentActivity>([
  'analyzing',
  'speaking',
  'challenging',
  'revising',
])

const STAGE_ORDER: MeetingStage[] = [
  'intake',
  'agenda',
  'assessments',
  'debate',
  'revisions',
  'synthesis',
  'persisted',
]

export const STAGE_LABEL: Record<MeetingStage, string> = {
  intake: 'Intake',
  agenda: 'Agenda',
  assessments: 'Independent analysis',
  presentation: 'Positions',
  debate: 'Debate',
  revisions: 'Revisions',
  synthesis: 'Synthesis',
  persisted: 'Complete',
}

export function stageProgress(stage: MeetingStage | null): number {
  if (!stage) return 0
  const index = STAGE_ORDER.indexOf(stage)
  if (index === -1) return 0
  return Math.round((index / (STAGE_ORDER.length - 1)) * 100)
}

export { STAGE_ORDER }
