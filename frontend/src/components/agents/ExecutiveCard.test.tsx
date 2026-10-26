import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ExecutiveCard } from './ExecutiveCard'
import { EXECUTIVE_PORTRAITS } from '@/assets/executives'
import type { ExecutiveDefinition } from '@/types/agents'

const cfo: ExecutiveDefinition = {
  agent_id: 'cfo',
  display_name: 'Yusuf Benali',
  title: 'Chief Financial Officer',
  short_title: 'CFO',
  expertise_descriptor: 'Runway, unit economics, and capital allocation',
  role_summary: 'Financial discipline and capital management.',
  responsibilities: ['Cash runway', 'Unit economics'],
  distinctive_perspective: 'Prioritizes economic viability.',
  personality: 'Analytical.',
  tool_scopes: ['financial', 'company'],
  can_chair: false,
  can_consult_one_on_one: true,
  theme_color: '#3F9E7C',
  theme_color_soft: '#85CDB1',
  symbol: 'ledger',
  avatar_ref: 'cfo',
}

describe('ExecutiveCard', () => {
  it('renders the name, title and expertise descriptor', () => {
    render(<ExecutiveCard executive={cfo} />)
    expect(screen.getByText('Yusuf Benali')).toBeInTheDocument()
    expect(screen.getByText('Chief Financial Officer')).toBeInTheDocument()
    expect(
      screen.getByText('Runway, unit economics, and capital allocation'),
    ).toBeInTheDocument()
  })

  it('renders an illustrated portrait rather than a placeholder', () => {
    const { container } = render(<ExecutiveCard executive={cfo} />)
    const svg = container.querySelector('svg[role="img"]')
    expect(svg).toBeTruthy()
    expect(svg?.getAttribute('aria-label')).toContain('Yusuf Benali')
    // A real illustration, not one shape standing in for a face.
    expect(container.querySelectorAll('svg path').length).toBeGreaterThan(5)
  })

  it('shows no status chip when idle', () => {
    render(<ExecutiveCard executive={cfo} />)
    expect(screen.queryByText('Speaking')).not.toBeInTheDocument()
  })

  it('surfaces a backend-driven status', () => {
    render(<ExecutiveCard executive={cfo} status="researching" />)
    expect(screen.getByText('Researching')).toBeInTheDocument()
  })

  it('reports selection through aria-pressed when interactive', () => {
    const onClick = vi.fn()
    render(<ExecutiveCard executive={cfo} selected onClick={onClick} />)
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true')
  })

  it('hides the descriptor in compact mode', () => {
    render(<ExecutiveCard executive={cfo} compact />)
    expect(
      screen.queryByText('Runway, unit economics, and capital allocation'),
    ).not.toBeInTheDocument()
  })

  it('fails loudly if an executive has no registered portrait', () => {
    const broken = { ...cfo, avatar_ref: 'nonexistent' }
    expect(() => render(<ExecutiveCard executive={broken} />)).toThrow(/No portrait/)
  })
})

describe('portrait registry', () => {
  it('covers all nine executives', () => {
    expect(Object.keys(EXECUTIVE_PORTRAITS)).toHaveLength(9)
  })

  it('gives every portrait a distinct component', () => {
    const unique = new Set(Object.values(EXECUTIVE_PORTRAITS))
    expect(unique.size).toBe(9)
  })
})
