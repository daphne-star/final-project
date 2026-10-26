import { Eyes, HEAD, Neck, PortraitFrame, type FigureProps } from './frame'

/**
 * Hana Watanabe, Customer Advocate.
 * Warm and open: rounded shoulders, a knit with a scarf, and a wide halo of
 * curls. The only figure with no hard corner anywhere in the silhouette.
 */
export function CustomerAdvocatePortrait({
  accent = '#C98B9B',
  accentSoft = '#E6BCC7',
  className,
}: Partial<FigureProps> & { className?: string }) {
  const skin = '#EBC9A4'
  const skinShade = '#CCA77F'
  const hair = '#241A18'
  const knit = '#3A2F36'

  return (
    <PortraitFrame
      accent={accent}
      accentSoft={accentSoft}
      symbol="heart"
      title="Illustrated portrait of Hana Watanabe, Customer Advocate"
      className={className}
    >
      {/* Rounded shoulders, no straight edges */}
      <path d="M150 238 q86 8 122 62 q16 26 16 100 H12 q0 -74 16 -100 q36 -54 122 -62 Z" fill={knit} />

      <Neck tone={skinShade} />

      {/* Scarf wound at the collar */}
      <path d="M106 258 q44 32 88 0 q12 18 2 32 q-46 28 -92 0 q-10 -14 2 -32 Z" fill={accent} />
      <path d="M192 290 q18 34 10 110 h-30 q12 -68 2 -104 Z" fill={accent} opacity="0.78" />
      <path d="M114 278 q-6 12 0 20 M136 288 q-4 9 0 16" stroke={accentSoft} strokeWidth="2.6" fill="none" opacity="0.75" />

      {/* Head */}
      <ellipse cx={HEAD.cx} cy={HEAD.cy} rx={HEAD.rx} ry={HEAD.ry} fill={skin} />

      {/* Halo of curls, built from overlapping circles */}
      <g fill={hair}>
        <circle cx="150" cy="80" r="29" />
        <circle cx="106" cy="102" r="26" />
        <circle cx="194" cy="102" r="26" />
        <circle cx="88" cy="142" r="22" />
        <circle cx="212" cy="142" r="22" />
        <circle cx="94" cy="180" r="17" />
        <circle cx="206" cy="180" r="17" />
      </g>
      <path d="M102 144 q6 -46 48 -48 q42 2 48 48 q-14 -32 -48 -32 q-34 0 -48 32 Z" fill={hair} />

      {/* Hoop earrings */}
      <g fill="none" stroke={accentSoft} strokeWidth="3">
        <circle cx="100" cy="176" r="9" />
        <circle cx="200" cy="176" r="9" />
      </g>

      <path d="M121 132 q13 -7 26 -1 M153 131 q13 -6 26 1" stroke={hair} strokeWidth="4" strokeLinecap="round" fill="none" />
      <Eyes y={150} spread={22} />
      <path d="M144 171 q6 5 12 0" stroke={skinShade} strokeWidth="2.4" fill="none" strokeLinecap="round" />
      {/* Open, attentive expression */}
      <path d="M137 187 q13 12 26 -1" stroke={skinShade} strokeWidth="3" fill="none" strokeLinecap="round" />
    </PortraitFrame>
  )
}
