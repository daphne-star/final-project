import { useQuery } from '@tanstack/react-query'

import { apiFetch } from './client'
import type { ExecutiveDefinition, HealthResponse } from '@/types/agents'

export const agentKeys = {
  all: ['agents'] as const,
  detail: (id: string) => ['agents', id] as const,
}

export function useExecutives() {
  return useQuery({
    queryKey: agentKeys.all,
    queryFn: () => apiFetch<ExecutiveDefinition[]>('/agents'),
    // The roster is fixed, so it never needs refetching within a session.
    staleTime: Infinity,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<HealthResponse>('/health'),
    refetchInterval: 30_000,
    retry: false,
  })
}
