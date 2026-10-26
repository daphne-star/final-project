import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Rosa Delgado, Chief Growth Officer.
 * The one deliberately asymmetric figure: head tilted, one shoulder dropped,
 * collar open, hair swept hard to one side. Reads as motion at a glance.
 */
export function CgoPortrait({
  accent = '#C86E4E',
  accentSoft = '#E5A287',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#D29C6E'
  const skinShade = '#B07A4E'
  const hair = '#2E1A14'
  const hairLight = '#45251B'
  const jacket = '#33272C'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="ascent"
      title="Illustrated portrait of Rosa Delgado, Chief Growth Officer"
      className={className}
    >
      {/* Asymmetric shoulders: one high, one dropped */}
      <path d="M148 238 C208 242 264 280 282 318 L288 400 L12 400 L26 278 C58 252 106 238 148 238 Z" fill={jacket} />

      <Neck tone={skinShade} />

      {/* Open collar, thrown off-centre */}
      <path d="M148 252 L104 400 L56 400 L110 288 Z" fill="#271D21" />
      <path d="M148 252 L200 400 L248 400 L190 296 Z" fill="#271D21" />
      <path d="M148 256 L132 310 L166 306 Z" fill={accent} opacity="0.9" />

      {/* Head, rotated into the tilt */}
      <g transform="rotate(-8 150 150)">
        <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

        {/* Volume piled to one side, falling past the shoulder */}
        <path d="M100 150 q-8 -84 50 -84 q46 0 56 46 q10 40 -4 68 q4 -46 -22 -62 q-30 -18 -56 2 q-18 14 -24 30 Z" fill={hair} />
        <path d="M198 148 q22 36 8 84 q-6 -44 -18 -62 Z" fill={hair} />
        <path d="M112 100 q34 -22 68 2 q-32 -10 -68 -2 Z" fill={hairLight} />

        <path d="M118 132 q13 -8 26 -2 M154 128 q13 -6 26 3" stroke={hair} strokeWidth="4" strokeLinecap="round" fill="none" />
        <Eyes y={149} spread={22} />
        <path d="M145 170 q6 6 12 0" stroke={skinShade} strokeWidth="2.4" fill="none" strokeLinecap="round" />
        {/* A slight, confident smile */}
        <path d="M136 186 q14 11 28 -2" stroke={skinShade} strokeWidth="3" fill="none" strokeLinecap="round" />
      </g>

      {/* Single statement earring */}
      <circle cx="204" cy="178" r="7" fill="none" stroke={accentSoft} strokeWidth="3.2" />
    </PortraitFrame>
  )
}
