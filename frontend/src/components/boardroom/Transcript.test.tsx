import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ParticipantRail } from './ParticipantRail'
import { Transcript } from './Transcript'
import { reduceEvents } from '@/lib/boardroomState'
import { EXEC_FIXTURES, fullMeetingEvents, partialFailureEvents } from '@/test/fixtures'

const executives = Object.values(EXEC_FIXTURES)

describe('Transcript', () => {
  it('renders every contribution from the event log', () => {
    const state = reduceEvents(fullMeetingEvents())
    render(<Transcript entries={state.transcript} executivesById={EXEC_FIXTURES} />)

    expect(screen.getByText('A launch is the only move that changes our position.')).toBeInTheDocument()
    expect(screen.getByText('A launch consumes runway we need for the next milestone.')).toBeInTheDocument()
    expect(screen.getByText('The runway argument is sound.')).toBeInTheDocument()
  })

  it('puts each message under the executive who produced it', () => {
    const state = reduceEvents(fullMeetingEvents())
    const { container } = render(
      <Transcript entries={state.transcript} executivesById={EXEC_FIXTURES} />,
    )

    const cfoEntries = container.querySelectorAll('[data-agent-id="cfo"]')
    expect(cfoEntries.length).toBeGreaterThan(0)
    // The CFO assessment names the CFO, not another executive.
    const assessment = container.querySelector(
      '[data-kind="assessment"][data-agent-id="cfo"]',
    )
    expect(assessment).toBeTruthy()
    expect(within(assessment as HTMLElement).getByText('Yusuf Benali')).toBeInTheDocument()
  })

  it('distinguishes Chair commentary from specialist analysis', () => {
    const state = reduceEvents(fullMeetingEvents())
    const { container } = render(
      <Transcript entries={state.transcript} executivesById={EXEC_FIXTURES} />,
    )

    const agenda = container.querySelector('[data-kind="agenda"]')
    const assessment = container.querySelector('[data-kind="assessment"]')
    expect(agenda).toBeTruthy()
    expect(assessment).toBeTruthy()

    // Chair turns are labelled as such and styled differently.
    expect(within(agenda as HTMLElement).getByText(/^Chair ·/)).toBeInTheDocument()
    expect(agenda?.className).toContain('border-dashed')
    expect(assessment?.className).not.toContain('border-dashed')
  })

  it('shows who an objection targets and the claim at issue', () => {
    const state = reduceEvents(fullMeetingEvents())
    const { container } = render(
      <Transcript entries={state.transcript} executivesById={EXEC_FIXTURES} />,
    )
    const objection = container.querySelector('[data-kind="objection"]') as HTMLElement
    expect(within(objection).getByText(/Challenging/)).toBeInTheDocument()
    expect(within(objection).getByText('Marcus Lindqvist')).toBeInTheDocument()
    expect(within(objection).getByText(/Launch the new product/)).toBeInTheDocument()
  })

  it('shows a revision as a change from one position to another', () => {
    const state = reduceEvents(fullMeetingEvents())
    const { container } = render(
      <Transcript entries={state.transcript} executivesById={EXEC_FIXTURES} />,
    )
    const revision = container.querySelector('[data-kind="revision"]') as HTMLElement
    expect(within(revision).getByText('Launch the new product.')).toBeInTheDocument()
    expect(
      within(revision).getByText('Stage the launch behind a retention push.'),
    ).toBeInTheDocument()
    expect(within(revision).getByText('position changed')).toBeInTheDocument()
  })

  it('renders an illustrated portrait beside each message', () => {
    const state = reduceEvents(fullMeetingEvents())
    const { container } = render(
      <Transcript entries={state.transcript} executivesById={EXEC_FIXTURES} />,
    )
    const portraits = container.querySelectorAll('svg[role="img"]')
    expect(portraits.length).toBe(state.transcript.length)
  })

  it('shows a failed contribution rather than hiding it', () => {
    const state = reduceEvents(partialFailureEvents())
    const { container } = render(
      <Transcript entries={state.transcript} executivesById={EXEC_FIXTURES} />,
    )
    const failure = container.querySelector('[data-kind="failure"]') as HTMLElement
    expect(failure).toBeTruthy()
    expect(within(failure).getByText(/503/)).toBeInTheDocument()
  })
})

describe('ParticipantRail', () => {
  it('shows each executive with the activity the backend reported', () => {
    const state = reduceEvents(fullMeetingEvents())
    const { container } = render(
      <ParticipantRail executives={executives} activity={state.activity} />,
    )
    for (const id of ['ceo', 'coo', 'cfo', 'strategy_consultant']) {
      const row = container.querySelector(`[data-agent-id="${id}"]`)
      expect(row?.getAttribute('data-activity')).toBe('finished')
    }
  })

  it('reflects an in-progress activity mid-meeting', () => {
    const events = fullMeetingEvents().slice(0, 7) // through agent_started for the CEO
    const state = reduceEvents(events)
    const { container } = render(
      <ParticipantRail executives={executives} activity={state.activity} />,
    )
    expect(
      container.querySelector('[data-agent-id="ceo"]')?.getAttribute('data-activity'),
    ).toBe('analyzing')
    expect(
      container.querySelector('[data-agent-id="cfo"]')?.getAttribute('data-activity'),
    ).toBe('waiting')
  })

  it('marks a failed executive distinctly from a finished one', () => {
    const state = reduceEvents(partialFailureEvents())
    const { container } = render(
      <ParticipantRail executives={executives} activity={state.activity} />,
    )
    expect(
      container.querySelector('[data-agent-id="coo"]')?.getAttribute('data-activity'),
    ).toBe('skipped')
  })

  it('separates the Chair from the specialists', () => {
    render(<ParticipantRail executives={executives} activity={{}} />)
    // Query the section headings specifically: "Chair" also appears as the
    // chairperson's short title on their own row.
    expect(screen.getByRole('heading', { name: 'Chair' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Executives' })).toBeInTheDocument()

    const chairSection = screen.getByRole('heading', { name: 'Chair' }).parentElement
    expect(
      chairSection?.querySelectorAll('[data-agent-id]'),
    ).toHaveLength(1)
  })
})
