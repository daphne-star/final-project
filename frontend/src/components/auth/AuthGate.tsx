import { useState, type FormEvent } from 'react'
import { Loader2 } from 'lucide-react'

import { useLogin, useRegister } from '@/api/auth'
import { useMe } from '@/api/consultations'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * Minimal credential screen. Every consultation endpoint is org-scoped and
 * authenticated, so the app needs a real identity before it can do anything —
 * there is no anonymous mode to fall back on.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading, isError } = useMe()

  if (isLoading) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loader2 className="size-5 animate-spin text-ink-muted" />
      </div>
    )
  }

  if (isError || !me) return <AuthScreen />
  return <>{children}</>
}

function AuthScreen() {
  const [mode, setMode] = useState<'login' | 'register'>('register')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [company, setCompany] = useState('')

  const login = useLogin()
  const register = useRegister()
  const active = mode === 'login' ? login : register
  const error = active.error instanceof Error ? active.error.message : null

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (mode === 'login') login.mutate({ email, password })
    else register.mutate({ email, password, organization_name: company || undefined })
  }

  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="font-display text-xl">Ghost Board</CardTitle>
          <CardDescription>
            {mode === 'login'
              ? 'Sign in to reach your board.'
              : 'Create a workspace to convene your board.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-3">
            <Field
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              autoComplete="email"
              required
            />
            <Field
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={8}
              required
              hint={mode === 'register' ? 'At least 8 characters' : undefined}
            />
            {mode === 'register' && (
              <Field
                label="Company"
                value={company}
                onChange={setCompany}
                placeholder="Northstar Labs"
              />
            )}

            {error && (
              <p role="alert" className="text-sm text-critical">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={active.isPending}>
              {active.isPending && <Loader2 className="animate-spin" />}
              {mode === 'login' ? 'Sign in' : 'Create workspace'}
            </Button>
          </form>

          <button
            type="button"
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
            className="mt-4 w-full text-center text-xs text-ink-muted transition-colors hover:text-ink"
          >
            {mode === 'login'
              ? 'No account? Create a workspace'
              : 'Already have an account? Sign in'}
          </button>
        </CardContent>
      </Card>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  hint,
  className,
  ...props
}: {
  label: string
  value: string
  onChange: (v: string) => void
  hint?: string
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'>) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-ink-muted">{label}</span>
      <input
        {...props}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink',
          'placeholder:text-ink-faint focus:border-accent focus:outline-none',
          className,
        )}
      />
      {hint && <span className="mt-1 block text-xs text-ink-faint">{hint}</span>}
    </label>
  )
}
