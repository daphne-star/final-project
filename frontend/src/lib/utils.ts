import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const TOKEN_FORMAT = new Intl.NumberFormat()

/**
 * Token counts, grouped. Exact rather than abbreviated: this is the figure a
 * founder checks against a provider bill, and "104.3k" is not that figure.
 */
export function formatTokens(count: number): string {
  return `${TOKEN_FORMAT.format(count)} token${count === 1 ? '' : 's'}`
}
