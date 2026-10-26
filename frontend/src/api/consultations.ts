import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from './client'
import type {
  ConsultationDetail,
  ConsultationSummary,
  MeResponse,
  TurnResponse,
} from '@/types/consultations'

export const consultationKeys = {
  all: ['consultations'] as const,
  list: (agentId?: string) => ['consultations', { agentId }] as const,
  detail: (id: string) => ['consultations', id] as const,
}

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<MeResponse>('/me'),
    retry: false,
  })
}

export function useConsultations(agentId?: string) {
  return useQuery({
    queryKey: consultationKeys.list(agentId),
    queryFn: () =>
      apiFetch<ConsultationSummary[]>(
        agentId ? `/consultations?agent_id=${encodeURIComponent(agentId)}` : '/consultations',
      ),
  })
}

export function useConsultation(id: string | undefined) {
  return useQuery({
    queryKey: consultationKeys.detail(id ?? ''),
    queryFn: () => apiFetch<ConsultationDetail>(`/consultations/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateConsultation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { agent_id: string; title?: string; opening_message?: string }) =>
      apiFetch<ConsultationDetail>('/consultations', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      qc.setQueryData(consultationKeys.detail(data.id), data)
      void qc.invalidateQueries({ queryKey: consultationKeys.all })
    },
  })
}

export function useSendMessage(consultationId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content: string) =>
      apiFetch<TurnResponse>(`/consultations/${consultationId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      }),
    onSuccess: (turn) => {
      // Append both sides locally so the thread updates without a refetch,
      // then revalidate against the server as the source of truth.
      qc.setQueryData<ConsultationDetail>(
        consultationKeys.detail(consultationId),
        (prev) =>
          prev
            ? { ...prev, messages: [...prev.messages, turn.user_message, turn.agent_message] }
            : prev,
      )
      void qc.invalidateQueries({ queryKey: consultationKeys.detail(consultationId) })
    },
  })
}
