import { useRef, useState, type FormEvent } from 'react'
import {
  AlertCircle,
  Check,
  FileText,
  Loader2,
  Plus,
  Search,
  Trash2,
  Upload,
} from 'lucide-react'

import {
  PROVENANCE_LABEL,
  VERIFIED_SOURCES,
  useCompanyProfile,
  useConfirmMemory,
  useCorrectMemory,
  useCreateMemory,
  useDeleteDocument,
  useDeleteMemory,
  useDocuments,
  useKnowledgeSearch,
  useMemories,
  useSaveCompanyProfile,
  useUploadDocument,
  type CompanyProfile,
  type Memory,
} from '@/api/knowledge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

export function CompanyIntelligencePage() {
  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-10 lg:py-12">
      <header className="mb-8">
        <h1 className="font-display text-3xl tracking-tight">Company intelligence</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
          What the board knows about your business, and where each piece came from.
          Nothing an agent infers becomes a fact until you say so.
        </p>
      </header>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="memory">Knowledge</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <ProfileForm />
        </TabsContent>
        <TabsContent value="documents">
          <DocumentsPanel />
        </TabsContent>
        <TabsContent value="memory">
          <MemoryPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// --------------------------------------------------------------------------

const EMPTY_PROFILE: CompanyProfile = {
  company_name: '',
  industry: null,
  business_model: null,
  stage: null,
  headcount: null,
  description: null,
  revenue_model: null,
  arr_usd: null,
  monthly_burn_usd: null,
  cash_on_hand_usd: null,
  runway_months: null,
  annual_churn_rate: null,
  goals: [],
  challenges: [],
  constraints: [],
}

function ProfileForm() {
  const { data, isLoading } = useCompanyProfile()
  const save = useSaveCompanyProfile()
  const [draft, setDraft] = useState<CompanyProfile | null>(null)

  const profile = draft ?? data ?? EMPTY_PROFILE
  function set<K extends keyof CompanyProfile>(key: K, value: CompanyProfile[K]) {
    setDraft({ ...profile, [key]: value })
  }

  if (isLoading) return <Loader2 className="size-5 animate-spin text-ink-muted" />

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate(profile, { onSuccess: () => setDraft(null) })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <p className="text-xs text-ink-muted">
        Everything here is treated as a fact you have confirmed. Leave a field blank
        rather than guessing — the board is told explicitly what it does not know.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name" value={profile.company_name} onChange={(v) => set('company_name', v)} required />
        <Field label="Industry" value={profile.industry ?? ''} onChange={(v) => set('industry', v || null)} />
        <Field label="Stage" value={profile.stage ?? ''} onChange={(v) => set('stage', v || null)} placeholder="Series A" />
        <NumberField label="Headcount" value={profile.headcount} onChange={(v) => set('headcount', v)} />
      </div>

      <TextArea
        label="What the company does"
        value={profile.description ?? ''}
        onChange={(v) => set('description', v || null)}
      />

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
          Financials
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumberField label="ARR (USD)" value={profile.arr_usd} onChange={(v) => set('arr_usd', v)} />
          <NumberField label="Monthly burn (USD)" value={profile.monthly_burn_usd} onChange={(v) => set('monthly_burn_usd', v)} />
          <NumberField label="Cash on hand (USD)" value={profile.cash_on_hand_usd} onChange={(v) => set('cash_on_hand_usd', v)} />
          <NumberField label="Runway (months)" value={profile.runway_months} onChange={(v) => set('runway_months', v)} />
          <NumberField
            label="Annual churn (0–1)"
            value={profile.annual_churn_rate}
            onChange={(v) => set('annual_churn_rate', v)}
            step="0.01"
          />
          <Field label="Revenue model" value={profile.revenue_model ?? ''} onChange={(v) => set('revenue_model', v || null)} />
        </div>
      </div>

      <ListField label="Goals" items={profile.goals} onChange={(v) => set('goals', v)} />
      <ListField label="Challenges" items={profile.challenges} onChange={(v) => set('challenges', v)} />

      {save.isError && (
        <p role="alert" className="text-sm text-critical">
          {save.error instanceof Error ? save.error.message : 'Could not save'}
        </p>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={save.isPending || !profile.company_name}>
          {save.isPending && <Loader2 className="animate-spin" />}
          Save profile
        </Button>
        {save.isSuccess && !draft && (
          <span className="flex items-center gap-1 text-xs text-positive">
            <Check className="size-3" />
            Saved
          </span>
        )}
      </div>
    </form>
  )
}

// --------------------------------------------------------------------------

function DocumentsPanel() {
  const { data: documents, isLoading } = useDocuments()
  const upload = useUploadDocument()
  const remove = useDeleteDocument()
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="space-y-5">
      <div className="rounded-card border border-dashed border-line-strong p-5 text-center">
        <Upload className="mx-auto size-5 text-ink-faint" />
        <p className="mt-2 text-sm text-ink">Upload a PDF, DOCX, or text file</p>
        <p className="mt-1 text-xs text-ink-muted">
          Text is extracted, split, and indexed so the board can cite it. Scanned
          PDFs need OCR and will be rejected.
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) upload.mutate(file)
            e.target.value = ''
          }}
        />
        <Button
          type="button"
          variant="outline"
          className="mt-3"
          disabled={upload.isPending}
          onClick={() => inputRef.current?.click()}
        >
          {upload.isPending ? <Loader2 className="animate-spin" /> : <Upload />}
          Choose a file
        </Button>
        {upload.isError && (
          <p role="alert" className="mt-2 text-xs text-critical">
            {upload.error instanceof Error ? upload.error.message : 'Upload failed'}
          </p>
        )}
      </div>

      {isLoading && <Loader2 className="size-5 animate-spin text-ink-muted" />}

      {documents?.length === 0 && (
        <p className="text-sm italic text-ink-faint">
          No documents yet. The board only knows what you have told it.
        </p>
      )}

      <ul className="space-y-2">
        {documents?.map((doc) => (
          <li
            key={doc.id}
            className="flex items-center gap-3 rounded-card border border-line bg-surface p-3"
          >
            <FileText className="size-4 shrink-0 text-ink-faint" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-ink">{doc.filename}</p>
              <p className="text-xs text-ink-faint">
                {(doc.size_bytes / 1024).toFixed(0)} KB · {doc.chunk_count} chunk
                {doc.chunk_count === 1 ? '' : 's'}
              </p>
              {doc.error_message && (
                <p className="mt-0.5 text-xs text-critical">{doc.error_message}</p>
              )}
            </div>
            <Badge variant={doc.status === 'indexed' ? 'positive' : 'caution'}>
              {doc.status}
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Delete ${doc.filename}`}
              onClick={() => remove.mutate(doc.id)}
            >
              <Trash2 />
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}

// --------------------------------------------------------------------------

function MemoryPanel() {
  const [showSuperseded, setShowSuperseded] = useState(false)
  const { data: memories, isLoading } = useMemories(showSuperseded)
  const create = useCreateMemory()
  const [key, setKey] = useState('')
  const [value, setValue] = useState('')
  const [query, setQuery] = useState('')
  const search = useKnowledgeSearch(query)

  function add(e: FormEvent) {
    e.preventDefault()
    if (!key.trim() || !value.trim()) return
    create.mutate(
      { key: key.trim(), value: value.trim() },
      {
        onSuccess: () => {
          setKey('')
          setValue('')
        },
      },
    )
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-faint">
          <Search className="size-3.5" />
          What would the board retrieve?
        </h2>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search company knowledge"
          placeholder="Try a question you would ask the board…"
          className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
        />
        {search.data && (
          <div className="mt-2 space-y-2">
            <p className="text-xs text-ink-muted">{search.data.note}</p>
            {search.data.hits.map((hit, i) => (
              <div key={i} className="rounded-md border border-line bg-surface p-2.5">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-xs text-ink">{hit.source}</span>
                  <Badge
                    variant={hit.is_verified ? 'positive' : 'caution'}
                    className="ml-auto"
                  >
                    {hit.provenance_label}
                  </Badge>
                </div>
                <p className="text-xs leading-relaxed text-ink-muted">{hit.excerpt}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
          Record a fact
        </h2>
        <form onSubmit={add} className="flex flex-col gap-2 sm:flex-row">
          <input
            value={key}
            onChange={(e) => setKey(e.target.value)}
            aria-label="Fact label"
            placeholder="Label, e.g. churn_breakdown"
            className="rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent sm:w-56"
          />
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-label="Fact value"
            placeholder="Enterprise renews at 96%; churn is self-serve."
            className="flex-1 rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
          />
          <Button type="submit" disabled={create.isPending || !key.trim() || !value.trim()}>
            {create.isPending ? <Loader2 className="animate-spin" /> : <Plus />}
            Add
          </Button>
        </form>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
            Stored knowledge
          </h2>
          <label className="flex items-center gap-1.5 text-xs text-ink-muted">
            <input
              type="checkbox"
              checked={showSuperseded}
              onChange={(e) => setShowSuperseded(e.target.checked)}
            />
            Show corrected
          </label>
        </div>

        {isLoading && <Loader2 className="size-5 animate-spin text-ink-muted" />}
        {memories?.length === 0 && (
          <p className="text-sm italic text-ink-faint">Nothing recorded yet.</p>
        )}

        <ul className="space-y-2">
          {memories?.map((memory) => (
            <MemoryRow key={memory.id} memory={memory} />
          ))}
        </ul>
      </section>
    </div>
  )
}

function MemoryRow({ memory }: { memory: Memory }) {
  const confirm = useConfirmMemory()
  const correct = useCorrectMemory()
  const remove = useDeleteMemory()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(memory.value)

  const verified = VERIFIED_SOURCES.has(memory.source_kind)

  return (
    <li
      data-provenance={memory.source_kind}
      className={cn(
        'rounded-card border bg-surface p-3',
        memory.superseded ? 'border-dashed border-line opacity-60' : 'border-line',
      )}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-ink">{memory.key}</span>
        <Badge variant={verified ? 'positive' : 'caution'}>
          {PROVENANCE_LABEL[memory.source_kind]}
        </Badge>
        {memory.superseded && <Badge variant="default">Corrected</Badge>}
      </div>

      {editing ? (
        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            aria-label={`Corrected value for ${memory.key}`}
            className="flex-1 rounded-md border border-line bg-canvas px-2 py-1 text-sm text-ink focus:border-accent"
          />
          <Button
            size="sm"
            onClick={() =>
              correct.mutate(
                { id: memory.id, value: draft },
                { onSuccess: () => setEditing(false) },
              )
            }
          >
            Save
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <p className="text-sm leading-relaxed text-ink-muted">{memory.value}</p>
      )}

      {!memory.superseded && !editing && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {!verified && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => confirm.mutate(memory.id)}
              disabled={confirm.isPending}
            >
              <Check />
              Confirm as fact
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            Correct
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => remove.mutate(memory.id)}
            disabled={remove.isPending}
          >
            <Trash2 />
            Delete
          </Button>
        </div>
      )}
    </li>
  )
}

// --------------------------------------------------------------------------

function Field({
  label,
  value,
  onChange,
  ...props
}: {
  label: string
  value: string
  onChange: (v: string) => void
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'>) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      <input
        {...props}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
      />
    </label>
  )
}

function NumberField({
  label,
  value,
  onChange,
  step,
}: {
  label: string
  value: number | null
  onChange: (v: number | null) => void
  step?: string
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      <input
        type="number"
        step={step}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
        className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink focus:border-accent"
      />
    </label>
  )
}

function TextArea({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className="w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink focus:border-accent"
      />
    </label>
  )
}

function ListField({
  label,
  items,
  onChange,
}: {
  label: string
  items: { text: string }[]
  onChange: (v: { text: string }[]) => void
}) {
  const [draft, setDraft] = useState('')
  return (
    <div>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
        {label}
      </h2>
      <ul className="mb-2 space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-ink-muted">
            <span className="flex-1">{item.text}</span>
            <button
              type="button"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
              className="text-ink-faint hover:text-critical"
              aria-label={`Remove ${item.text}`}
            >
              <Trash2 className="size-3.5" />
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              if (draft.trim()) {
                onChange([...items, { text: draft.trim() }])
                setDraft('')
              }
            }
          }}
          aria-label={`Add a ${label.toLowerCase().replace(/s$/, '')}`}
          placeholder={`Add a ${label.toLowerCase().replace(/s$/, '')}…`}
          className="flex-1 rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:border-accent"
        />
      </div>
    </div>
  )
}

export function MissingProfileNotice() {
  return (
    <div className="flex items-start gap-2 rounded-card border border-caution/40 bg-caution/10 p-3">
      <AlertCircle className="mt-0.5 size-4 shrink-0 text-caution" />
      <p className="text-sm text-ink-muted">
        No company profile yet. The board will say it does not know rather than
        guessing, which makes for short meetings.
      </p>
    </div>
  )
}
