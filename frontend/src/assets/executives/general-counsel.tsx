import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Eleanor Whitfield, General Counsel.
 * Formal and restrained: a low tight bun, a perfectly straight shoulder line,
 * and a pleated jabot at the collar. The most contained figure on the board.
 */
export function GeneralCounselPortrait({
  accent = '#9AA3AD',
  accentSoft = '#C5CCD3',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#E6C7AC'
  const skinShade = '#C5A286'
  const hair = '#3A3630'
  const robe = '#23262B'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="scales"
      title="Illustrated portrait of Eleanor Whitfield, General Counsel"
      className={className}
    >
      {/* One unbroken horizontal shoulder line */}
      <path d="M150 238 L210 252 L258 278 L258 400 L42 400 L42 278 L90 252 Z" fill={robe} />
      <path d="M42 278 h216" stroke="#2F333A" strokeWidth="3" />

      <Neck tone={skinShade} width={18} />

      {/* Pleated jabot, stepping down the chest */}
      <path d="M150 250 L126 270 L150 282 L174 270 Z" fill={accentSoft} />
      <path d="M130 278 h40 l-4 20 h-32 Z" fill={accentSoft} opacity="0.85" />
      <path d="M134 298 h32 l-5 20 h-22 Z" fill={accentSoft} opacity="0.72" />
      <path d="M150 282 v36" stroke="#8A939D" strokeWidth="1.6" opacity="0.7" />

      {/* Head */}
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

      {/* Hair pulled flat into a low bun */}
      <path d="M100 146 q-2 -74 50 -74 q52 0 50 74 q-10 -40 -50 -40 q-40 0 -50 40 Z" fill={hair} />
      <path d="M100 146 q-2 30 6 46 q-16 -20 -6 -46 Z" fill={hair} />
      <path d="M200 146 q2 30 -6 46 q16 -20 6 -46 Z" fill={hair} />
      <ellipse cx="150" cy="202" rx="22" ry="16" fill={hair} />
      <path d="M122 92 q28 -14 56 0" stroke="#4A463E" strokeWidth="2.6" fill="none" strokeLinecap="round" />

      {/* Level, unhurried brow */}
      <path d="M120 132 h24 M156 132 h24" stroke={hair} strokeWidth="3.6" strokeLinecap="round" />
      <Eyes y={150} spread={22} />
      <path d="M145 171 q5 5 10 0" stroke={skinShade} strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M140 188 h20" stroke={skinShade} strokeWidth="2.8" strokeLinecap="round" />
    </PortraitFrame>
  )
}
