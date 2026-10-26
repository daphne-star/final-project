import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Priya Raghunathan, Chief Operating Officer.
 * Utilitarian: a flat square shoulder line, a working vest with webbing
 * straps, hair tied back, and an earpiece. Dressed to be on the floor.
 */
export function CooPortrait({
  accent = '#5B7FA6',
  accentSoft = '#9DBBD8',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#B07B52'
  const skinShade = '#926341'
  const hair = '#1C1613'
  const vest = '#2B3447'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="gears"
      title="Illustrated portrait of Priya Raghunathan, Chief Operating Officer"
      className={className}
    >
      {/* Flat square shoulders — no taper anywhere */}
      <path d="M150 238 L206 248 L270 280 L270 400 L30 400 L30 280 L94 248 Z" fill={vest} />

      <Neck tone={skinShade} />

      {/* Vest panel, straps, buckles */}
      <path d="M150 252 L108 296 L108 400 L192 400 L192 296 Z" fill="#232B3B" />
      <path d="M122 288 L122 400 M178 288 L178 400" stroke={accent} strokeWidth="5" opacity="0.7" />
      <rect x="114" y="330" width="16" height="11" rx="2" fill={accentSoft} opacity="0.8" />
      <rect x="170" y="330" width="16" height="11" rx="2" fill={accentSoft} opacity="0.8" />
      <path d="M150 252 L132 288 L168 288 Z" fill="#1A2030" />

      {/* Head */}
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

      {/* Hair pulled back flat, tied behind */}
      <path d="M100 148 q-2 -76 50 -76 q52 0 50 76 q-10 -42 -50 -42 q-40 0 -50 42 Z" fill={hair} />
      <path d="M100 148 q-6 34 2 54 q-14 -26 -2 -54 Z" fill={hair} />
      <path d="M200 148 q6 34 -2 54 q14 -26 2 -54 Z" fill={hair} />
      <path d="M196 170 q22 14 16 48 q-4 -30 -20 -40 Z" fill={hair} />

      {/* Earpiece: the operational tell */}
      <circle cx="202" cy="158" r="8" fill={accentSoft} />
      <path d="M202 166 q12 18 -4 30" stroke={accentSoft} strokeWidth="3.4" fill="none" strokeLinecap="round" />

      <path d="M119 132 q13 -7 26 -2 M155 130 q13 -5 26 2" stroke={hair} strokeWidth="4" strokeLinecap="round" fill="none" />
      <Eyes y={149} spread={22} />
      <path d="M144 170 q6 5 12 0" stroke={skinShade} strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M139 187 h22" stroke={skinShade} strokeWidth="3" strokeLinecap="round" />
    </PortraitFrame>
  )
}
