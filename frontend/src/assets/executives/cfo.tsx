import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Yusuf Benali, Chief Financial Officer.
 * Refined and reserved: the narrowest shoulders on the board, a buttoned
 * waistcoat, round spectacles, and a close-trimmed beard.
 */
export function CfoPortrait({
  accent = '#3F9E7C',
  accentSoft = '#85CDB1',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#C68B5E'
  const skinShade = '#A5704A'
  const hair = '#211A14'
  const suit = '#222C2A'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="ledger"
      title="Illustrated portrait of Yusuf Benali, Chief Financial Officer"
      className={className}
    >
      {/* Narrow sloped shoulders */}
      <path d="M150 240 C192 242 230 276 244 308 L254 400 L46 400 L56 308 C70 276 108 242 150 240 Z" fill={suit} />

      <Neck tone={skinShade} width={18} />

      {/* Waistcoat with a precise button run */}
      <path d="M150 254 L112 300 L108 400 L192 400 L188 300 Z" fill="#1A2322" />
      <path d="M150 254 L128 304 M150 254 L172 304" stroke={accent} strokeWidth="3.4" opacity="0.75" fill="none" />
      <g fill={accentSoft} opacity="0.85">
        <circle cx="150" cy="326" r="3.6" />
        <circle cx="150" cy="350" r="3.6" />
        <circle cx="150" cy="374" r="3.6" />
      </g>

      {/* Head */}
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

      {/* Neat side part */}
      <path d="M100 144 q-2 -74 50 -74 q52 0 50 74 q-10 -40 -50 -40 q-30 0 -42 18 Z" fill={hair} />
      <path d="M100 144 q-4 26 2 40 q-10 -20 -2 -40 Z" fill={hair} />
      <path d="M200 144 q4 26 -2 40 q10 -20 2 -40 Z" fill={hair} />

      {/* Close-trimmed beard following the jaw */}
      <path d="M102 156 q4 50 48 52 q44 -2 48 -52 q-8 36 -48 38 q-40 -2 -48 -38 Z" fill={hair} />
      <path d="M132 184 q18 9 36 0 q-6 24 -18 24 q-12 0 -18 -24 Z" fill={hair} />
      <path d="M138 180 q12 6 24 0" stroke={skinShade} strokeWidth="2.6" fill="none" strokeLinecap="round" />

      {/* Round spectacles */}
      <g fill="none" stroke={accentSoft} strokeWidth="2.8">
        <circle cx="128" cy="148" r="17" />
        <circle cx="172" cy="148" r="17" />
        <path d="M145 148 h10" />
        <path d="M111 142 l-11 -5 M189 142 l11 -5" />
      </g>
      <Eyes y={149} spread={22} />
    </PortraitFrame>
  )
}
