import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Marcus Lindqvist, Chief Executive Officer.
 * Forward-looking: broad squared shoulders, deep notched lapels, and hair
 * swept back off the face. The widest silhouette on the board.
 */
export function CeoPortrait({
  accent = '#C9A227',
  accentSoft = '#E8CE74',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#E8C4A0'
  const skinShade = '#CA9F77'
  const hair = '#4A3B2A'
  const hairLight = '#5E4C36'
  const suit = '#23283A'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="compass"
      title="Illustrated portrait of Marcus Lindqvist, Chief Executive Officer"
      className={className}
    >
      {/* Broad, squared shoulders */}
      <path d="M150 238 C208 240 258 272 278 304 L288 400 L12 400 L22 304 C42 272 92 240 150 238 Z" fill={suit} />

      <Neck tone={skinShade} width={21} />

      {/* Shirt wedge and notched lapels */}
      <path d="M150 252 L118 290 L150 400 L182 290 Z" fill="#DCDCE2" opacity="0.92" />
      <path d="M150 252 L104 282 L62 400 L132 400 Z" fill="#1A1E2C" />
      <path d="M150 252 L196 282 L238 400 L168 400 Z" fill="#1A1E2C" />
      <path d="M150 262 L136 300 L150 400 L164 300 Z" fill={accent} opacity="0.9" />

      {/* Head */}
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

      {/* Swept-back hair with a visible part */}
      <path d="M100 142 q-4 -76 50 -76 q54 0 50 76 q-8 -42 -50 -42 q-42 0 -50 42 Z" fill={hair} />
      <path d="M104 118 q28 -26 70 -14 q22 6 26 24 q-16 -22 -44 -22 q-34 0 -52 12 Z" fill={hairLight} />
      <path d="M100 142 q-4 26 2 40 q-10 -20 -2 -40 Z" fill={hair} />
      <path d="M200 142 q4 26 -2 40 q10 -20 2 -40 Z" fill={hair} />

      {/* Jaw */}
      <path d="M108 164 q6 44 42 46 q36 -2 42 -46" fill="none" stroke={skinShade} strokeWidth="2" opacity="0.45" />

      <path d="M118 130 q13 -6 26 -1 M156 129 q13 -5 26 1" stroke={hair} strokeWidth="4" strokeLinecap="round" fill="none" />
      <Eyes y={149} spread={22} />
      <path d="M144 170 q6 6 12 0" stroke={skinShade} strokeWidth="2.4" fill="none" strokeLinecap="round" />
      <path d="M139 187 q11 7 22 -1" stroke={skinShade} strokeWidth="3" fill="none" strokeLinecap="round" />
    </PortraitFrame>
  )
}
