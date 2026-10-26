/** Fixture events mirroring what the orchestrator actually emits. */

import type { ExecutiveDefinition } from '@/types/agents'
import type { MeetingEvent, MeetingEventType } from '@/types/meetings'

let seq = 0

export function resetSeq() {
  seq = 0
}

export function ev(
  event_type: MeetingEventType,
  agent_id: string | null = null,
  payload: Record<string, unknown> = {},
  sequence?: number,
): MeetingEvent {
  seq = sequence ?? seq + 1
  return {
    event_id: `evt-${seq}`,
    meeting_id: 'meeting-1',
    sequence_number: seq,
    event_type,
    agent_id,
    payload,
    timestamp: new Date(1_700_000_000_000 + seq * 1000).toISOString(),
  }
}

/** A complete meeting: agenda, four assessments, two challenges, a revision, a brief. */
export function fullMeetingEvents(): MeetingEvent[] {
  resetSeq()
  return [
    ev('meeting_started', null, { question: 'Retention, expansion, or a new product?' }),
    ev('stage_changed', null, { stage: 'agenda' }),
    ev('agent_started', 'chairperson', { stage: 'agenda' }),
    ev('agenda_created', 'chairperson', {
      reframed_question: 'Which priority best protects revenue over 12 months?',
      agenda_items: [
        { title: 'Runway impact', question: 'What does each option cost?', why_it_matters: 'x' },
        { title: 'Capacity', question: 'Can 28 people execute it?', why_it_matters: 'y' },
      ],
      participants: ['ceo', 'coo', 'cfo', 'strategy_consultant'],
      tensions_to_test: ['Growth ambition against delivery capacity'],
    }),
    ev('stage_changed', null, { stage: 'assessments' }),
    ev('agent_status_changed', 'ceo', { status: 'speaking' }),
    ev('agent_started', 'ceo', { stage: 'assessment' }),
    ev('agent_message_completed', 'ceo', {
      stage: 'assessment',
      summary: 'A launch is the only move that changes our position.',
      recommended_position: 'Launch the new product.',
      confidence_level: 'medium',
    }),
    ev('agent_message_completed', 'cfo', {
      stage: 'assessment',
      summary: 'A launch is not affordable on a 12-month runway.',
      recommended_position: 'Improve retention.',
      confidence_level: 'high',
    }),
    ev('agent_message_completed', 'coo', {
      stage: 'assessment',
      summary: 'We lack the delivery capacity for a launch.',
      recommended_position: 'Improve retention.',
      confidence_level: 'medium',
    }),
    ev('agent_message_completed', 'strategy_consultant', {
      stage: 'assessment',
      summary: 'The question is a false choice.',
      recommended_position: 'Reframe: these are not mutually exclusive.',
      confidence_level: 'low',
    }),
    ev('stage_changed', null, { stage: 'debate' }),
    ev('agent_message_completed', 'chairperson', {
      stage: 'debate_plan',
      conflicts_found: true,
      rationale: 'The CEO wants a launch; the CFO says it is unfundable.',
      assignment_count: 2,
    }),
    ev('objection_raised', 'cfo', {
      target_agent_id: 'ceo',
      stance: 'challenge',
      challenged_claim: 'Launch the new product.',
      objection: 'A launch consumes runway we need for the next milestone.',
      severity: 'major',
    }),
    ev('objection_raised', 'coo', {
      target_agent_id: 'ceo',
      stance: 'partially_agree',
      challenged_claim: 'Launch the new product.',
      objection: 'Delivery capacity is already committed through the quarter.',
      severity: 'moderate',
    }),
    ev('stage_changed', null, { stage: 'revisions' }),
    ev('position_revised', 'ceo', {
      position_changed: true,
      original_position: 'Launch the new product.',
      updated_position: 'Stage the launch behind a retention push.',
      reason_for_change: 'The runway argument is sound.',
    }),
    ev('stage_changed', null, { stage: 'synthesis' }),
    ev('decision_generated', 'chairperson', {
      recommended_option_id: 'retention',
      option_count: 2,
      dissent_count: 1,
      confidence_level: 'medium',
    }),
    ev('meeting_completed', null, {
      model_requests: 10,
      total_tokens: 12_000,
      assessments: 4,
      objections: 2,
      revisions: 1,
      agent_failures: [],
    }),
  ]
}

/** A meeting where one agent fails and the meeting still completes. */
export function partialFailureEvents(): MeetingEvent[] {
  resetSeq()
  return [
    ev('meeting_started', null, {}),
    ev('agenda_created', 'chairperson', {
      reframed_question: 'Q',
      agenda_items: [],
      participants: ['ceo', 'coo'],
      tensions_to_test: [],
    }),
    ev('agent_failed', 'coo', { stage: 'assessment', error: 'ModelHTTPError: 503' }),
    ev('agent_status_changed', 'coo', { status: 'skipped' }),
    ev('agent_message_completed', 'ceo', {
      stage: 'assessment',
      summary: 'Still a view.',
      recommended_position: 'Do the thing.',
      confidence_level: 'low',
    }),
    ev('meeting_completed', null, { model_requests: 3 }),
  ]
}

/** A meeting the founder interrupts, and the executive answers. */
export function interventionEvents(): MeetingEvent[] {
  resetSeq()
  return [
    ev('meeting_started', null, {}),
    ev('agenda_created', 'chairperson', {
      reframed_question: 'Q',
      agenda_items: [],
      participants: ['ceo', 'coo'],
      tensions_to_test: [],
    }),
    ev('meeting_paused', null, { stage: 'assessments' }),
    ev('user_intervention_requested', 'coo', {
      kind: 'challenge',
      prompt: 'Can we really do this in six months?',
      about_agent_id: null,
    }),
    ev('intervention_answered', 'coo', {
      kind: 'challenge',
      answer: 'Not at current capacity. Six months assumes two new hires.',
      confidence_level: 'high',
    }),
    ev('meeting_resumed', null, { stage: 'assessments' }),
    ev('meeting_completed', null, { model_requests: 5 }),
  ]
}

export function failedMeetingEvents(): MeetingEvent[] {
  resetSeq()
  return [
    ev('meeting_started', null, {}),
    ev('agent_failed', 'chairperson', { stage: 'agenda', error: 'timeout' }),
    ev('meeting_failed', null, {
      code: 'agenda_failed',
      reason: 'The Chairperson could not produce an agenda.',
    }),
  ]
}

export const EXEC_FIXTURES: Record<string, ExecutiveDefinition> = Object.fromEntries(
  (
    [
      ['chairperson', 'Adaeze Okonkwo', 'Board Chairperson', 'Chair', '#7C5CD6', true],
      ['ceo', 'Marcus Lindqvist', 'Chief Executive Officer', 'CEO', '#C9A227', false],
      ['coo', 'Priya Raghunathan', 'Chief Operating Officer', 'COO', '#5B7FA6', false],
      ['cfo', 'Yusuf Benali', 'Chief Financial Officer', 'CFO', '#3F9E7C', false],
      [
        'strategy_consultant',
        'Idris Mensah',
        'Outside Strategy Consultant',
        'Consultant',
        '#3E9A9A',
        false,
      ],
    ] as const
  ).map(([id, name, title, short, color, canChair]) => [
    id,
    {
      agent_id: id,
      display_name: name,
      title,
      short_title: short,
      expertise_descriptor: 'desc',
      role_summary: 'summary',
      responsibilities: ['a'],
      distinctive_perspective: 'perspective',
      personality: 'personality',
      tool_scopes: ['company'],
      can_chair: canChair,
      can_consult_one_on_one: !canChair,
      theme_color: color,
      theme_color_soft: color,
      symbol: 'gavel',
      avatar_ref: id,
    } satisfies ExecutiveDefinition,
  ]),
)
