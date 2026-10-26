import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Adaeze Okonkwo, Board Chairperson.
 * Balanced and symmetrical: a centred crown of hair over a ceremonial stand
 * collar. Nothing on this figure leans left or right.
 */
export function ChairpersonPortrait({
  accent = '#7C5CD6',
  accentSoft = '#B9A4F0',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#6B4332'
  const skinShade = '#553427'
  const hair = '#1A1520'
  const robe = '#2A2140'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="gavel"
      title="Illustrated portrait of Adaeze Okonkwo, Board Chairperson"
      className={className}
    >
      {/* Robe: symmetric trapezoid, shoulders square to the frame */}
      <path d="M150 238 C200 240 248 270 266 302 L282 400 L18 400 L34 302 C52 270 100 240 150 238 Z" fill={robe} />
      <path d="M150 238 C200 240 248 270 266 302 L282 400 L150 400 Z" fill="#000" opacity="0.12" />

      <Neck tone={skinShade} />

      {/* Stand collar, closing over the neck */}
      <path d="M112 254 L150 296 L188 254 L176 242 L150 266 L124 242 Z" fill={accent} />
      <path d="M150 296 v36" stroke={accentSoft} strokeWidth="2.5" opacity="0.6" />
      <circle cx="150" cy="338" r="8" fill={accentSoft} opacity="0.75" />

      {/* Head */}
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

      {/* Centred crown, symmetric bun */}
      <path d="M100 150 q-2 -74 50 -74 q52 0 50 74 q-10 -40 -50 -40 q-40 0 -50 40 Z" fill={hair} />
      <ellipse cx="150" cy="70" rx="23" ry="17" fill={hair} />
      <path d="M100 150 q-4 32 4 48 q-12 -24 -4 -48 Z" fill={hair} />
      <path d="M200 150 q4 32 -4 48 q12 -24 4 -48 Z" fill={hair} />

      {/* Level brow: composed, impartial */}
      <path d="M118 131 h24 M158 131 h24" stroke={hair} strokeWidth="4" strokeLinecap="round" />
      <Eyes y={149} spread={22} />
      <path d="M144 170 q6 5 12 0" stroke={skinShade} strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M140 186 q10 6 20 0" stroke={skinShade} strokeWidth="3" fill="none" strokeLinecap="round" />
    </PortraitFrame>
  )
}
