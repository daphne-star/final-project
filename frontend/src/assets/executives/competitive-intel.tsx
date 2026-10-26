import { Eyes, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Tomas Varga, Competitive Intelligence Advisor.
 * Angular and watchful: a high upturned coat collar, a faceted hexagonal
 * head rather than an oval, and narrowed eyes. No curves anywhere.
 */
export function CompetitiveIntelPortrait({
  accent = '#5A5FC7',
  accentSoft = '#9B9EE4',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#DDB593'
  const skinShade = '#BB9170'
  const hair = '#151321'
  const coat = '#1E2136'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="chess_knight"
      title="Illustrated portrait of Tomas Varga, Competitive Intelligence Advisor"
      className={className}
    >
      {/* Angular shoulders */}
      <path d="M150 238 L202 250 L272 300 L286 400 L14 400 L28 300 L98 250 Z" fill={coat} />

      <Neck tone={skinShade} />

      {/* Upturned collar, framing the jaw in two hard planes */}
      <path d="M118 256 L96 212 L74 316 L132 290 Z" fill="#171A2B" />
      <path d="M182 256 L204 212 L226 316 L168 290 Z" fill="#171A2B" />
      <path d="M150 288 L126 292 L150 400 L174 292 Z" fill="#171A2B" />
      <path d="M96 216 L78 310 M204 216 L222 310" stroke={accent} strokeWidth="3" opacity="0.65" fill="none" />

      {/* Faceted head: hexagon, not an ellipse */}
      <path d="M150 90 L198 120 L200 166 L150 208 L100 166 L102 120 Z" fill={skin} />
      <path d="M100 166 L150 176 L200 166 L150 208 Z" fill={skinShade} opacity="0.4" />

      {/* Slicked hair, hard diagonal sweep */}
      <path d="M102 124 L150 86 L198 124 L196 140 L150 112 L104 148 Z" fill={hair} />
      <path d="M104 148 L150 112 L196 140 L196 126 L150 94 L102 122 Z" fill={hair} />

      <path d="M116 140 l24 5 M160 145 l24 -5" stroke={hair} strokeWidth="4" strokeLinecap="round" />
      <Eyes y={158} spread={22} narrow />
      <path d="M145 176 l5 6 l5 -6" stroke={skinShade} strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M138 192 h24" stroke={skinShade} strokeWidth="2.8" strokeLinecap="round" />
    </PortraitFrame>
  )
}
