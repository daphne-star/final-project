import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Idris Mensah, Outside Strategy Consultant.
 * Geometric and independent: a turtleneck instead of a suit, a precise high
 * fade with a hard flat crown, and rectangular glasses. Visibly not staff.
 */
export function StrategyConsultantPortrait({
  accent = '#3E9A9A',
  accentSoft = '#85C9C9',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#7A4F35'
  const skinShade = '#613D27'
  const hair = '#14110F'
  const hairEdge = '#262019'
  const knit = '#1F2E2E'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="prism"
      title="Illustrated portrait of Idris Mensah, Outside Strategy Consultant"
      className={className}
    >
      {/* Turtleneck: one clean shape, no lapels, no tie */}
      <path d="M150 236 C202 238 246 272 262 302 L272 400 L28 400 L38 302 C54 272 98 238 150 236 Z" fill={knit} />

      <Neck tone={skinShade} />

      {/* Rolled collar sitting over the neck */}
      <path d="M108 236 q42 30 84 0 l8 38 q-50 30 -100 0 Z" fill="#26393A" />
      <path d="M114 250 q36 24 72 0" stroke={accent} strokeWidth="2.8" fill="none" opacity="0.7" />

      {/* Head */}
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

      {/* High fade: flat crown with a hard edge, not a curve */}
      <path d="M100 126 L100 108 q0 -28 50 -28 q50 0 50 28 l0 18 q-14 -14 -50 -14 q-36 0 -50 14 Z" fill={hair} />
      <path d="M100 126 q12 -12 50 -12 q38 0 50 12 l0 10 q-16 -12 -50 -12 q-34 0 -50 12 Z" fill={hairEdge} />

      {/* Rectangular glasses */}
      <g fill="none" stroke={accentSoft} strokeWidth="3">
        <rect x="108" y="136" width="38" height="25" rx="3" />
        <rect x="154" y="136" width="38" height="25" rx="3" />
        <path d="M146 147 h8" />
        <path d="M108 142 l-10 -4 M192 142 l10 -4" />
      </g>
      <Eyes y={149} spread={22} />

      {/* Trimmed geometric goatee */}
      <path d="M136 182 h28 l-6 24 h-16 Z" fill={hair} />
      <path d="M138 180 q12 7 24 0" stroke={skinShade} strokeWidth="2.6" fill="none" strokeLinecap="round" />
    </PortraitFrame>
  )
}
