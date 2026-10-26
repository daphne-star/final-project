import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch, getAuthToken } from './client'

export type FactSource =
  | 'user_confirmed'
  | 'imported_evidence'
  | 'model_interpretation'
  | 'hypothesis'
  | 'estimate'
  | 'historical_decision'

export interface DocumentSummary {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  status: 'uploaded' | 'processing' | 'indexed' | 'failed'
  error_message: string | null
  chunk_count: number
  created_at: string
}

export interface Memory {
  id: string
  key: string
  value: string
  category: string | null
  source_kind: FactSource
  confidence: number | null
  superseded: boolean
  confirmed_at: string | null
  origin_meeting_id: string | null
  origin_document_id: string | null
  created_at: string
}

export interface KnowledgeHit {
  source: string
  excerpt: string
  provenance: FactSource
  provenance_label: string
  is_verified: boolean
  rank: number
}

export interface KnowledgeSearch {
  query: string
  hits: KnowledgeHit[]
  verified_count: number
  note: string
}

export interface CompanyProfile {
  company_name: string
  industry: string | null
  business_model: string | null
  stage: string | null
  headcount: number | null
  description: string | null
  revenue_model: string | null
  arr_usd: number | null
  monthly_burn_usd: number | null
  cash_on_hand_usd: number | null
  runway_months: number | null
  annual_churn_rate: number | null
  goals: { text: string }[]
  challenges: { text: string }[]
  constraints: { text: string }[]
}

export function useCompanyProfile() {
  return useQuery({
    queryKey: ['company-profile'],
    queryFn: () => apiFetch<CompanyProfile | null>('/company-profile'),
  })
}

export function useSaveCompanyProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CompanyProfile) =>
      apiFetch<CompanyProfile>('/company-profile', {
        method: 'PUT',
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['company-profile'] }),
  })
}

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: () => apiFetch<DocumentSummary[]>('/documents'),
  })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    // Not apiFetch: multipart needs the browser to set its own boundary, so
    // the Content-Type header must be left alone.
    mutationFn: async (file: File) => {
      const body = new FormData()
      body.append('file', file)
      const headers: Record<string, string> = {}
      const token = getAuthToken()
      if (token) headers.Authorization = `Bearer ${token}`

      const res = await fetch('/api/documents', { method: 'POST', headers, body })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.error?.message ?? `Upload failed (${res.status})`)
      }
      return (await res.json()) as DocumentSummary
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['documents'] })
      void qc.invalidateQueries({ queryKey: ['knowledge'] })
    },
  })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/documents/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['documents'] })
      void qc.invalidateQueries({ queryKey: ['knowledge'] })
    },
  })
}

export function useMemories(includeSuperseded = false) {
  return useQuery({
    queryKey: ['memory', { includeSuperseded }],
    queryFn: () =>
      apiFetch<Memory[]>(`/memory?include_superseded=${includeSuperseded}`),
  })
}

function invalidateKnowledge(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['memory'] })
  void qc.invalidateQueries({ queryKey: ['knowledge'] })
}

export function useCreateMemory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { key: string; value: string; category?: string }) =>
      apiFetch<Memory>('/memory', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => invalidateKnowledge(qc),
  })
}

export function useConfirmMemory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Memory>(`/memory/${id}/confirm`, { method: 'POST' }),
    onSuccess: () => invalidateKnowledge(qc),
  })
}

export function useCorrectMemory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      apiFetch<Memory>(`/memory/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ value }),
      }),
    onSuccess: () => invalidateKnowledge(qc),
  })
}

export function useDeleteMemory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/memory/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidateKnowledge(qc),
  })
}

export function useKnowledgeSearch(query: string) {
  return useQuery({
    queryKey: ['knowledge', query],
    queryFn: () =>
      apiFetch<KnowledgeSearch>(`/knowledge/search?q=${encodeURIComponent(query)}`),
    enabled: query.trim().length > 1,
  })
}

export const PROVENANCE_LABEL: Record<FactSource, string> = {
  user_confirmed: 'Confirmed by you',
  imported_evidence: 'From a document',
  model_interpretation: 'Inferred by an agent',
  hypothesis: 'Hypothesis',
  estimate: 'Estimate',
  historical_decision: 'Past decision',
}

/** Which provenances count as something the board may rely on. */
export const VERIFIED_SOURCES: ReadonlySet<FactSource> = new Set<FactSource>([
  'user_confirmed',
  'imported_evidence',
  'historical_decision',
])
