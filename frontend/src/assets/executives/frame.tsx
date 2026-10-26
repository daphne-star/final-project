import * as React from 'react'

/**
 * Shared chrome for every executive portrait.
 *
 * The illustration system is deliberately constrained: flat vector shapes, a
 * two-tone palette driven by the executive's accent color, one emblem behind
 * the figure, and a paper grain over the whole card. Individual portraits only
 * supply the figure, so nine very different silhouettes still read as one set.
 */

export const PORTRAIT_WIDTH = 300
export const PORTRAIT_HEIGHT = 400

export interface FigureProps {
  /** Primary accent, from the backend roster. */
  accent: string
  /** Lighter companion tone used for highlights and the emblem. */
  accentSoft: string
}

export type SymbolName =
  | 'gavel'
  | 'compass'
  | 'gears'
  | 'ledger'
  | 'ascent'
  | 'heart'
  | 'chess_knight'
  | 'scales'
  | 'prism'

/**
 * Emblems sit behind the figure at low opacity. Each is drawn on a 0 0 100 100
 * grid and scaled by the frame, so they share weight and optical size.
 */
export const EMBLEMS: Record<SymbolName, React.ReactNode> = {
  gavel: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <rect x="30" y="18" width="40" height="20" rx="3" transform="rotate(-35 50 28)" />
      <path d="M58 38 L78 68" />
      <path d="M22 72 h40" />
    </g>
  ),
  compass: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="50" cy="50" r="32" />
      <path d="M62 38 L44 46 L38 62 L56 54 Z" />
      <path d="M50 12 v6 M50 82 v6 M12 50 h6 M82 50 h6" />
    </g>
  ),
  gears: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="38" cy="42" r="18" />
      <circle cx="38" cy="42" r="6" />
      <circle cx="68" cy="64" r="13" />
      <circle cx="68" cy="64" r="4" />
      <path d="M38 18 v6 M38 60 v6 M14 42 h6 M56 42 h6 M21 25 l4 4 M51 55 l4 4" />
    </g>
  ),
  ledger: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <rect x="22" y="18" width="56" height="64" rx="4" />
      <path d="M36 18 v64" />
      <path d="M46 34 h22 M46 48 h22 M46 62 h14" />
    </g>
  ),
  ascent: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 74 L38 52 L54 64 L84 28" />
      <path d="M68 28 h16 v16" />
      <circle cx="50" cy="84" r="3" fill="currentColor" stroke="none" />
    </g>
  ),
  heart: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <path d="M50 80 C20 58 18 36 32 28 C42 22 50 30 50 38 C50 30 58 22 68 28 C82 36 80 58 50 80 Z" />
    </g>
  ),
  chess_knight: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <path d="M34 82 h36 l-4 -12 c8 -14 6 -34 -8 -42 l4 -10 l-12 4 l-6 -8 l-4 12 c-12 6 -16 18 -16 26 l10 -6 l6 8 l-8 10 Z" />
      <circle cx="54" cy="34" r="2.5" fill="currentColor" stroke="none" />
    </g>
  ),
  scales: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <path d="M50 16 v62" />
      <path d="M22 30 h56" />
      <path d="M50 78 h-14 M50 78 h14" />
      <path d="M22 30 L12 52 a12 12 0 0 0 20 0 Z" />
      <path d="M78 30 L68 52 a12 12 0 0 0 20 0 Z" />
    </g>
  ),
  prism: (
    <g fill="none" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round">
      <path d="M50 16 L82 76 H18 Z" />
      <path d="M8 46 L34 46" />
      <path d="M62 58 L92 48 M64 66 L94 62 M60 50 L90 34" />
    </g>
  ),
}

interface PortraitFrameProps extends FigureProps {
  symbol: SymbolName
  children: React.ReactNode
  /** Rendered into <title> for screen readers. */
  title: string
  className?: string
}

export function PortraitFrame({
  accent,
  accentSoft,
  symbol,
  children,
  title,
  className,
}: PortraitFrameProps) {
  // Collision-safe ids: several portraits render on one page.
  const uid = React.useId().replace(/:/g, '')

  return (
    <svg
      viewBox={`0 0 ${PORTRAIT_WIDTH} ${PORTRAIT_HEIGHT}`}
      className={className}
      role="img"
      aria-label={title}
      preserveAspectRatio="xMidYMid slice"
    >
      <title>{title}</title>
      <defs>
        <linearGradient id={`bg-${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.34" />
          <stop offset="55%" stopColor={accent} stopOpacity="0.14" />
          <stop offset="100%" stopColor="#070a11" stopOpacity="0.9" />
        </linearGradient>

        <radialGradient id={`halo-${uid}`} cx="50%" cy="34%" r="52%">
          <stop offset="0%" stopColor={accentSoft} stopOpacity="0.30" />
          <stop offset="100%" stopColor={accentSoft} stopOpacity="0" />
        </radialGradient>

        <filter id={`grain-${uid}`} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="7" />
          <feColorMatrix type="saturate" values="0" />
          <feComponentTransfer>
            <feFuncA type="linear" slope="0.5" />
          </feComponentTransfer>
        </filter>

        <clipPath id={`clip-${uid}`}>
          <rect x="0" y="0" width={PORTRAIT_WIDTH} height={PORTRAIT_HEIGHT} />
        </clipPath>
      </defs>

      <g clipPath={`url(#clip-${uid})`}>
        <rect width={PORTRAIT_WIDTH} height={PORTRAIT_HEIGHT} fill="#0b0e16" />
        <rect width={PORTRAIT_WIDTH} height={PORTRAIT_HEIGHT} fill={`url(#bg-${uid})`} />
        <rect width={PORTRAIT_WIDTH} height={PORTRAIT_HEIGHT} fill={`url(#halo-${uid})`} />

        {/* Emblem, high behind the figure so the head never sits inside it */}
        <g
          transform="translate(90 10) scale(1.2)"
          color={accentSoft}
          stroke={accentSoft}
          opacity="0.13"
        >
          {EMBLEMS[symbol]}
        </g>

        {children}

        {/* Paper grain over everything */}
        <rect
          width={PORTRAIT_WIDTH}
          height={PORTRAIT_HEIGHT}
          filter={`url(#grain-${uid})`}
          opacity="0.10"
          style={{ mixBlendMode: 'overlay' }}
        />

        {/* Base vignette so card text below stays legible */}
        <rect
          y={PORTRAIT_HEIGHT - 110}
          width={PORTRAIT_WIDTH}
          height="110"
          fill="url(#fade)"
        />
        <defs>
          <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0b0e16" stopOpacity="0" />
            <stop offset="100%" stopColor="#0b0e16" stopOpacity="0.85" />
          </linearGradient>
        </defs>
      </g>
    </svg>
  )
}

/**
 * Shared bust geometry. Every portrait uses these so nine different figures
 * line up when shown side by side in a grid.
 *
 *   crown  y ≈  90    top of the skull
 *   eyes   y ≈ 150
 *   chin   y ≈ 206
 *   neck   y   196 → 258  (overlaps the chin so the two shapes never separate)
 *   collar y ≈ 248        shoulders start here and run off the bottom edge
 */
export const HEAD = { cx: 150, cy: 148, rx: 50, ry: 58 } as const
export const NECK_TOP = 196
export const SHOULDER_TOP = 238

/** Neck and jaw shadow. Drawn before the head so the chin overlaps it. */
export function Neck({ tone, width = 19 }: { tone: string; width?: number }) {
  return (
    <path
      d={`M${150 - width} ${NECK_TOP} h${width * 2} v${SHOULDER_TOP + 14 - NECK_TOP} q-${width} 12 -${width * 2} 0 Z`}
      fill={tone}
    />
  )
}

/** Eyes shared across portraits; expression comes from the brow and lid shapes. */
export function Eyes({
  cx = 150,
  y = 150,
  spread = 21,
  tone = '#1b2130',
  narrow = false,
}: {
  cx?: number
  y?: number
  spread?: number
  tone?: string
  narrow?: boolean
}) {
  const ry = narrow ? 2 : 3.4
  return (
    <g fill={tone}>
      <ellipse cx={cx - spread} cy={y} rx={4} ry={ry} />
      <ellipse cx={cx + spread} cy={y} rx={4} ry={ry} />
    </g>
  )
}
