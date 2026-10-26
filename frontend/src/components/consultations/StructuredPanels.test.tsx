import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StructuredPanels } from './StructuredPanels'
import type { ConsultationStructured } from '@/types/consultations'

const base: ConsultationStructured = {
  answer: 'Prioritise retention.',
  key_points: ['Churn is 15% annually', 'Runway is 12 months'],
  assumptions: [
    {
      statement: 'The burn figure is current',
      why_it_matters: 'Runway changes if it is stale',
      how_to_validate: 'Check the latest bank balance',
    },
  ],
  risks: [
    {
      description: 'Cuts could weaken delivery',
      severity: 'major',
      likelihood: 'medium',
      mitigation: 'Stage the reductions',
    },
  ],
  open_questions: [
    {
      question: 'Is that logo or revenue churn?',
      why_it_matters: 'They imply different fixes',
      who_should_answer: 'customer_advocate',
    },
  ],
  recommended_actions: [
    {
      description: 'Build a downside cash forecast',
      priority: 'critical',
      suggested_owner: 'Finance',
      rough_timeline: 'next 30 days',
    },
  ],
  confidence_level: 'medium',
  out_of_scope: false,
  refer_to_agent_id: null,
}

describe('StructuredPanels', () => {
  it('renders every section of a full structured answer', () => {
    render(<StructuredPanels data={base} accent="#3F9E7C" />)

    expect(screen.getByText('Key points')).toBeInTheDocument()
    expect(screen.getByText('Churn is 15% annually')).toBeInTheDocument()
    expect(screen.getByText('Recommended actions')).toBeInTheDocument()
    expect(screen.getByText('Build a downside cash forecast')).toBeInTheDocument()
    expect(screen.getByText('Risks')).toBeInTheDocument()
    expect(screen.getByText('Cuts could weaken delivery')).toBeInTheDocument()
    expect(screen.getByText('Assumptions')).toBeInTheDocument()
    expect(screen.getByText('The burn figure is current')).toBeInTheDocument()
    expect(screen.getByText('Open questions')).toBeInTheDocument()
    expect(screen.getByText('Is that logo or revenue churn?')).toBeInTheDocument()
  })

  it('surfaces assumptions rather than burying them', () => {
    render(<StructuredPanels data={base} accent="#3F9E7C" />)
    // The validation step is shown, not just the assumption itself.
    expect(screen.getByText(/Check the latest bank balance/)).toBeInTheDocument()
    expect(screen.getByText('Runway changes if it is stale')).toBeInTheDocument()
  })

  it('shows severity and priority badges', () => {
    render(<StructuredPanels data={base} accent="#3F9E7C" />)
    expect(screen.getByText('major')).toBeInTheDocument()
    expect(screen.getByText('critical')).toBeInTheDocument()
  })

  it('always reports the confidence level', () => {
    render(<StructuredPanels data={base} accent="#3F9E7C" />)
    expect(screen.getByText('Confidence')).toBeInTheDocument()
    expect(screen.getByText('medium')).toBeInTheDocument()
  })

  it('renders nothing when the agent returned no structure', () => {
    const empty: ConsultationStructured = {
      ...base,
      key_points: [],
      assumptions: [],
      risks: [],
      open_questions: [],
      recommended_actions: [],
    }
    const { container } = render(<StructuredPanels data={empty} accent="#3F9E7C" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('omits sections the agent left empty', () => {
    const partial: ConsultationStructured = { ...base, risks: [], open_questions: [] }
    render(<StructuredPanels data={partial} accent="#3F9E7C" />)
    expect(screen.getByText('Key points')).toBeInTheDocument()
    expect(screen.queryByText('Risks')).not.toBeInTheDocument()
    expect(screen.queryByText('Open questions')).not.toBeInTheDocument()
  })
})
