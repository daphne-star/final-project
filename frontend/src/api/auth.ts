import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch, setAuthToken } from './client'

interface TokenResponse {
  access_token: string
  token_type: string
  expires_in_minutes: number
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      apiFetch<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      setAuthToken(data.access_token)
      void qc.invalidateQueries()
    },
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      email: string
      password: string
      full_name?: string
      organization_name?: string
    }) =>
      apiFetch<TokenResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      setAuthToken(data.access_token)
      void qc.invalidateQueries()
    },
  })
}

export function logout(qc: ReturnType<typeof useQueryClient>) {
  setAuthToken(null)
  qc.clear()
}
