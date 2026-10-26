/** Thin fetch wrapper. Dev requests go through the Vite proxy to FastAPI. */

const BASE = '/api'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

let authToken: string | null = localStorage.getItem('gb_token')

export function setAuthToken(token: string | null) {
  authToken = token
  if (token) localStorage.setItem('gb_token', token)
  else localStorage.removeItem('gb_token')
}

export function getAuthToken() {
  return authToken
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)

  const res = await fetch(`${BASE}${path}`, { ...init, headers })

  if (!res.ok) {
    // The backend returns { error: { code, message } } for every failure.
    let code = `http_${res.status}`
    let message = res.statusText
    try {
      const body = await res.json()
      if (body?.error) {
        code = body.error.code ?? code
        message = body.error.message ?? message

        // A bare "Request validation failed" tells the user nothing about
        // which field is wrong, so unpack FastAPI's per-field detail.
        const fieldErrors = body.error.details?.errors
        if (Array.isArray(fieldErrors) && fieldErrors.length > 0) {
          message = fieldErrors
            .map((e: { loc?: unknown[]; msg?: string }) => {
              const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : undefined
              return field ? `${field}: ${e.msg}` : e.msg
            })
            .filter(Boolean)
            .join('; ')
        }
      }
    } catch {
      // Non-JSON error body; keep the status text.
    }
    throw new ApiError(res.status, code, message)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
