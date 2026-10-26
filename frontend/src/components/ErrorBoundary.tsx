import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
  /** Shown in the message so the user knows how much of the app is affected. */
  label?: string
}

interface State {
  error: Error | null
}

/**
 * Without this, one bad render blanks the page: React unmounts the whole tree
 * and the user is left on a white screen with the real error only in the
 * console. A meeting in progress keeps running on the server either way, so
 * the honest message is "the view broke, your meeting did not".
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep the component stack: the message below deliberately does not show
    // it, but it is the only thing that makes the report actionable.
    console.error('Unhandled render error', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div role="alert" className="grid min-h-dvh place-items-center px-4">
        <div className="w-full max-w-md rounded-card border border-critical/40 bg-critical/10 p-5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-5 shrink-0 text-critical" />
            <h1 className="text-sm font-semibold text-ink">
              {this.props.label ?? 'Something broke in the interface'}
            </h1>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">
            This is a fault in the page, not in your data. Anything the board
            has already produced is saved on the server.
          </p>
          <p className="mt-2 break-words font-mono text-xs text-ink-faint">{error.message}</p>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" size="sm" onClick={() => this.setState({ error: null })}>
              Try again
            </Button>
            <Button variant="ghost" size="sm" onClick={() => window.location.reload()}>
              Reload the page
            </Button>
          </div>
        </div>
      </div>
    )
  }
}
