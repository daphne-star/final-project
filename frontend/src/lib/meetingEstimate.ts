/**
 * How many tokens a meeting is likely to cost, before it runs.
 *
 * Measured, not derived. The obvious route — predict the number of model
 * calls, multiply by a tokens-per-call figure — looked fine until it was
 * checked against real runs: the call formula (`2 + participants * 2`) says a
 * Full Board makes 18 calls, and the recorded one made 35, because it does
 * not account for debate rounds. Anything built on it inherits that error and
 * presents it as a token count someone might check against a bill.
 *
 * So this compares like with like instead: the median of what *this*
 * organization's past meetings in the *same mode* actually used. With no
 * same-mode history it widens to all modes, scaling each past meeting by how
 * much smaller or larger it was, and says that is what it did. With no
 * history at all it declines to estimate. The estimate improves as the board
 * is used, and the sample is always the user's own questions and company
 * profile.
 *
 * The scaling is a *ratio* of two numbers from the same biased estimator, so
 * the bias largely cancels — which is why it is safe here and was not safe as
 * an absolute multiplier.
 */

import type { MeetingMode } from '@/types/meetings'

export interface PastMeetingUsage {
  mode: MeetingMode
  totalTokens: number
}

export type EstimateBasis = 'same-mode' | 'all-modes'

export interface TokenEstimate {
  tokens: number
  /** How many past meetings it was learned from, for the user to judge it by. */
  sampleSize: number
  /** Whether those meetings were this mode, or any mode. */
  basis: EstimateBasis
}

/**
 * Median rather than mean: one Full Board over a long document should not
 * drag the estimate for every meeting that follows it.
 */
function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

/** Two significant figures, because the sample does not justify more. */
function roundToTwoFigures(value: number): number {
  if (value <= 0) return 0
  const magnitude = 10 ** (Math.floor(Math.log10(value)) - 1)
  return Math.round(value / magnitude) * magnitude
}

export interface EstimateOptions {
  /** Model calls this meeting is expected to make, at its current roster. */
  expectedCalls: number
  /** Model calls a typical meeting of some past mode makes. */
  callsForMode: (mode: MeetingMode) => number
}

export function estimateMeetingTokens(
  mode: MeetingMode,
  history: PastMeetingUsage[],
  { expectedCalls, callsForMode }: EstimateOptions,
): TokenEstimate | null {
  // A draft, or a meeting that failed before its first answer, records zero
  // and would drag any median it took part in towards nothing.
  const measured = history.filter((m) => m.totalTokens > 0)
  const sameMode = measured.filter((m) => m.mode === mode)

  if (sameMode.length > 0) {
    const middle = median(sameMode.map((m) => m.totalTokens))!
    return {
      tokens: roundToTwoFigures(middle),
      sampleSize: sameMode.length,
      basis: 'same-mode',
    }
  }

  // Nothing in this mode yet. A Quick Consultation and a Full Board differ by
  // more than four times, so an unscaled cross-mode median would tell someone
  // a one-executive meeting costs what a nine-agent board costs.
  const scaled = measured
    .map((m) => {
      const past = callsForMode(m.mode)
      return past > 0 ? (m.totalTokens * expectedCalls) / past : null
    })
    .filter((v): v is number => v !== null && Number.isFinite(v) && v > 0)

  const middle = median(scaled)
  if (middle === null) return null

  return { tokens: roundToTwoFigures(middle), sampleSize: scaled.length, basis: 'all-modes' }
}

/**
 * Model calls a meeting of this shape makes, assuming a single debate round.
 *
 * Only used where there is no history to measure, and shown as a call count
 * rather than converted to tokens — see the note at the top of this file.
 */
export function estimateModelCalls(participantCount: number): number {
  return 2 + participantCount * 2
}
