import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch, getAuthToken } from './client'
import type {
  Decision,
  Meeting,
  MeetingDetail,
  MeetingEvent,
  MeetingMode,
} from '@/types/meetings'
import type {
  ActionItemDetail,
  Intervention,
  InterventionKind,
} from '@/types/meetings'

export const meetingKeys = {
  all: ['meetings'] as const,
  detail: (id: string) => ['meetings', id] as const,
  events: (id: string) => ['meetings', id, 'events'] as const,
}

export function useMeetings() {
  return useQuery({
    queryKey: meetingKeys.all,
    queryFn: () => apiFetch<Meeting[]>('/meetings'),
  })
}

export function useMeeting(id: string | undefined, options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: meetingKeys.detail(id ?? ''),
    queryFn: () => apiFetch<MeetingDetail>(`/meetings/${id}`),
    enabled: Boolean(id),
    refetchInterval: options?.refetchInterval,
  })
}

/** Historical events, used to hydrate a page opened mid-meeting or after it ends. */
export function useMeetingEvents(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: meetingKeys.events(id ?? ''),
    queryFn: () => apiFetch<MeetingEvent[]>(`/meetings/${id}/events`),
    enabled: Boolean(id) && enabled,
  })
}

export function useCreateMeeting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      question: string
      title?: string
      start_immediately?: boolean
      participant_agent_ids?: string[]
      mode?: MeetingMode
      subject_decision_id?: string
    }) =>
      apiFetch<MeetingDetail>('/meetings', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (data) => {
      qc.setQueryData(meetingKeys.detail(data.id), data)
      void qc.invalidateQueries({ queryKey: meetingKeys.all })
    },
  })
}

export function useStartMeeting(meetingId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<Meeting>(`/meetings/${meetingId}/start`, { method: 'POST' }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: meetingKeys.detail(meetingId) })
    },
  })
}

export function useCancelMeeting(meetingId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<Meeting>(`/meetings/${meetingId}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: meetingKeys.detail(meetingId) })
    },
  })
}

export function useDecisions() {
  return useQuery({
    queryKey: ['decisions'],
    queryFn: () => apiFetch<Decision[]>('/decisions'),
  })
}

export function useDecision(id: string | undefined) {
  return useQuery({
    queryKey: ['decisions', id],
    queryFn: () => apiFetch<Decision>(`/decisions/${id}`),
    enabled: Boolean(id),
  })
}

export function useUpdateDecision(decisionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { status: string; decision_notes?: string }) =>
      apiFetch<Decision>(`/decisions/${decisionId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['decisions'] })
      void qc.invalidateQueries({ queryKey: meetingKeys.all })
    },
  })
}


export function useQueueIntervention(meetingId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      agent_id: string
      kind: InterventionKind
      prompt: string
      about_agent_id?: string
    }) =>
      apiFetch<Intervention>(`/meetings/${meetingId}/interventions`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: meetingKeys.detail(meetingId) })
    },
  })
}

export function usePauseMeeting(meetingId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<Meeting>(`/meetings/${meetingId}/pause`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: meetingKeys.detail(meetingId) }),
  })
}

export function useResumeMeeting(meetingId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<Meeting>(`/meetings/${meetingId}/resume`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: meetingKeys.detail(meetingId) }),
  })
}

export function useActionItems(openOnly = false) {
  return useQuery({
    queryKey: ['action-items', { openOnly }],
    queryFn: () => apiFetch<ActionItemDetail[]>(`/action-items?open_only=${openOnly}`),
  })
}

export function useUpdateActionItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; suggested_owner?: string; outcome_notes?: string }) =>
      apiFetch<ActionItemDetail>(`/action-items/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['action-items'] })
      void qc.invalidateQueries({ queryKey: ['decisions'] })
    },
  })
}

/** Download an export. Uses fetch directly so the blob can be saved. */
export async function downloadDecision(
  decisionId: string,
  format: 'markdown' | 'pdf',
): Promise<void> {
  const headers: Record<string, string> = {}
  const token = getAuthToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`/api/decisions/${decisionId}/export?format=${format}`, {
    headers,
  })
  if (!res.ok) throw new Error(`Export failed (${res.status})`)

  const disposition = res.headers.get('content-disposition') ?? ''
  const match = /filename="([^"]+)"/.exec(disposition)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = match?.[1] ?? `decision.${format === 'pdf' ? 'pdf' : 'md'}`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
