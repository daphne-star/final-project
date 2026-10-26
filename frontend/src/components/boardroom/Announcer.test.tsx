import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Announcer } from '@/components/boardroom/Announcer'
import type { TranscriptEntry } from '@/lib/boardroomState'
import type { ExecutiveDefinition } from '@/types/agents'

function exec(agent_id: string, display_name: string): ExecutiveDefinition {
  return {
    agent_id,
    display_name,
    title: display_name,
    short_title: display_name,
    mandate: '',
    avatar_ref: agent_id,
    theme_color: '#000000',
    theme_color_soft: '#111111',
    speaking_style: '',
    priorities: [],
    blind_spots: [],
    tools: [],
  } as unknown as ExecutiveDefinition
}

const EXECS: Record<string, ExecutiveDefinition> = {
  cfo: exec('cfo', 'Alex Chen'),
  coo: exec('coo', 'Marcus Webb'),
}

function entry(partial: Partial<TranscriptEntry> & { id: string }): TranscriptEntry {
  return {
    sequence: 1,
    kind: 'assessment',
    agentId: 'cfo',
    timestamp: '2026-01-01T00:00:00Z',
    title: 'Assessment',
    body: 'A long assessment body that no screen reader should have to sit through twice.',
    ...partial,
  }
}

const log = () => screen.getByRole('log')

describe('Announcer', () => {
  it('stays silent about turns that were already on screen when the page opened', () => {
    render(
      <Announcer
        stage="assessments"
        status="completed"
        transcript={[entry({ id: 'a' }), entry({ id: 'b', agentId: 'coo' })]}
        executivesById={EXECS}
      />,
    )
    expect(log()).toBeEmptyDOMElement()
  })

  it('announces a turn that arrives, by speaker and kind rather than by body', () => {
    const { rerender } = render(
      <Announcer stage="assessments" status="running" transcript={[]} executivesById={EXECS} />,
    )
    rerender(
      <Announcer
        stage="assessments"
        status="running"
        transcript={[entry({ id: 'a' })]}
        executivesById={EXECS}
      />,
    )
    expect(log()).toHaveTextContent('Assessment from Alex Chen.')
    // The point of announcing arrivals is that the body is NOT read out.
    expect(log()).not.toHaveTextContent('sit through twice')
  })

  it('names both sides of a challenge', () => {
    const { rerender } = render(
      <Announcer stage="debate" status="running" transcript={[]} executivesById={EXECS} />,
    )
    rerender(
      <Announcer
        stage="debate"
        status="running"
        transcript={[
          entry({ id: 'o', kind: 'objection', title: 'Objection', agentId: 'coo', targetAgentId: 'cfo' }),
        ]}
        executivesById={EXECS}
      />,
    )
    expect(log()).toHaveTextContent('Objection from Marcus Webb to Alex Chen.')
  })

  it('keeps the queue bounded so a long meeting does not replay itself', () => {
    const { rerender } = render(
      <Announcer stage="assessments" status="running" transcript={[]} executivesById={EXECS} />,
    )
    const many = Array.from({ length: 20 }, (_, i) => entry({ id: `e${i}` }))
    rerender(
      <Announcer
        stage="assessments"
        status="running"
        transcript={many}
        executivesById={EXECS}
      />,
    )
    expect(log().childElementCount).toBe(8)
  })

  it('reports terminal status in its own region, apart from the turn log', () => {
    const { rerender } = render(
      <Announcer stage="synthesis" status="running" transcript={[]} executivesById={EXECS} />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Stage: Synthesis')

    rerender(
      <Announcer stage="synthesis" status="failed" transcript={[]} executivesById={EXECS} />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('The meeting failed.')
  })

  it('falls back to the agent id when the executive roster has not loaded', () => {
    const { rerender } = render(
      <Announcer stage="agenda" status="running" transcript={[]} executivesById={{}} />,
    )
    rerender(
      <Announcer
        stage="agenda"
        status="running"
        transcript={[entry({ id: 'a', agentId: 'chairperson', title: 'Agenda' })]}
        executivesById={{}}
      />,
    )
    expect(log()).toHaveTextContent('Agenda from chairperson.')
  })
})
