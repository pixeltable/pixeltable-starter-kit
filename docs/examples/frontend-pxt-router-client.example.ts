/**
 * Reference client for calling /api/pxt ONLY (PR #1268-style).
 *
 * Best practice for this template: keep frontend/src/lib/api.ts → facades
 * (/api/data, /api/search, /api/agent). Use this file to understand raw router
 * shapes or to build admin/tools — NOT as the primary app client.
 */

const PXT = '/api/pxt'

// ── Shared ─────────────────────────────────────────────────────────────────

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(
      (body as { detail?: string }).detail ?? `HTTP ${res.status}`,
    )
  }
  return res.json() as Promise<T>
}

// ── Data: multipart insert (column names = schema, not "file") ─────────────

export type MediaKind = 'image' | 'document' | 'video'

const INSERT_PATH: Record<MediaKind, string> = {
  image: `${PXT}/tables/images/insert`,
  document: `${PXT}/tables/documents/insert`,
  video: `${PXT}/tables/videos/insert`,
}

const FILE_FIELD: Record<MediaKind, string> = {
  image: 'image',
  document: 'document',
  video: 'video',
}

/** Same idea as backend _classify_file — pick insert route. */
export function classifyMediaKind(filename: string): MediaKind {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return 'image'
  if (['mp4', 'mov', 'avi'].includes(ext)) return 'video'
  return 'document'
}

/**
 * Replaces api.uploadFile(file) — you must pick the route by type (extension/MIME).
 * PxtFastAPIRouter: upload columns → TempStore paths; other inputs → Form fields.
 */
export async function uploadFilePxt(
  file: File,
  kind: MediaKind,
): Promise<Record<string, unknown>> {
  const form = new FormData()
  form.append(FILE_FIELD[kind], file)
  // Timestamp must match Pixeltable Timestamp column; ISO string is typical for JSON APIs.
  form.append('timestamp', new Date().toISOString())

  const res = await fetch(INSERT_PATH[kind], { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<Record<string, unknown>>
}

/**
 * data-page.tsx today: api.getFiles() → { documents, images, videos }.
 * Pure Pxt router: no aggregated list — you would implement N queries or keep /api/data/files.
 */
export async function getFilesPxt_NOT_AVAILABLE(): Promise<never> {
  throw new Error(
    'No single PxtFastAPIRouter equivalent; keep GET /api/data/files or add custom aggregate.',
  )
}

// ── Search: four routes + merge into SearchResponse-like shape ─────────────

/** Multi-row query wrapper from add_query_route (one_row=false, return_scalar=false). */
type PxtQueryRows<R> = { rows: R[] }

/** Shapes follow setup_pixeltable @pxt.query select lists (abbrev.). */
type DocRow = {
  text: string
  source_doc: unknown
  sim: number
  title?: string
  heading?: string
  page_number?: number
}
type ImgRow = { encoded_image: string; sim: number }
type FrameRow = {
  encoded_frame: string
  source_video: unknown
  sim: number
}
type TranscriptRow = { text: string; source_video: unknown; sim: number }

/** Subset of frontend/src/types for standalone example. */
export type SearchResult = {
  type: 'document' | 'image' | 'video_frame' | 'transcript'
  uuid: string
  similarity: number
  text?: string
  thumbnail?: string | null
  metadata?: Record<string, unknown>
}

export type SearchResponse = {
  query: string
  results: SearchResult[]
}

export type QueryMetadata = {
  timestamp: string
  has_doc_context: boolean
  has_image_context: boolean
  has_tool_output: boolean
}

function basenamePath(p: unknown): string {
  const s = typeof p === 'string' ? p : String(p)
  return s.split(/[/\\]/).pop() ?? s
}

/**
 * Replaces api.search({ query, types, limit }) — fan-out + client merge/sort.
 * Paths must match your add_query_route registrations.
 */
export async function searchPxt(params: {
  queryText: string
  types: Set<string>
  limit: number
}): Promise<SearchResponse> {
  const q = params.queryText
  const limit = params.limit
  const types = params.types
  const results: SearchResult[] = []

  if (types.has('document')) {
    const res = await requestJson<PxtQueryRows<DocRow>>(
      `${PXT}/queries/documents`,
      {
        method: 'POST',
        body: JSON.stringify({ query_text: q }),
      },
    )
    for (const r of res.rows.slice(0, limit)) {
      results.push({
        type: 'document',
        uuid: '',
        similarity: Math.round(r.sim * 1000) / 1000,
        text: r.text,
        metadata: {
          title: r.title,
          source: basenamePath(r.source_doc),
        },
      })
    }
  }

  if (types.has('image')) {
    const res = await requestJson<PxtQueryRows<ImgRow>>(
      `${PXT}/queries/images`,
      { method: 'POST', body: JSON.stringify({ query_text: q }) },
    )
    for (const r of res.rows.slice(0, limit)) {
      results.push({
        type: 'image',
        uuid: '',
        similarity: Math.round(r.sim * 1000) / 1000,
        thumbnail: r.encoded_image,
        metadata: {},
      })
    }
  }

  if (types.has('video_frame')) {
    const res = await requestJson<PxtQueryRows<FrameRow>>(
      `${PXT}/queries/video_frames`,
      { method: 'POST', body: JSON.stringify({ query_text: q }) },
    )
    for (const r of res.rows.slice(0, limit)) {
      results.push({
        type: 'video_frame',
        uuid: '',
        similarity: Math.round(r.sim * 1000) / 1000,
        thumbnail: r.encoded_frame,
        metadata: { source: basenamePath(r.source_video) },
      })
    }
  }

  if (types.has('transcript')) {
    const res = await requestJson<PxtQueryRows<TranscriptRow>>(
      `${PXT}/queries/video_transcripts`,
      { method: 'POST', body: JSON.stringify({ query_text: q }) },
    )
    for (const r of res.rows.slice(0, limit)) {
      results.push({
        type: 'transcript',
        uuid: '',
        similarity: Math.round(r.sim * 1000) / 1000,
        text: r.text,
        metadata: { source: basenamePath(r.source_video) },
      })
    }
  }

  results.sort((a, b) => (b.similarity ?? 0) - (a.similarity ?? 0))
  return {
    query: q,
    results: results.slice(0, limit),
  }
}

// ── Agent: raw insert only (no chat_history, no QueryResponse DTO) ───────────

/** Mirror backend/config.py defaults for required insert columns. */
const AGENT_DEFAULTS = {
  initial_system_prompt:
    'Identify the best tool(s) to answer the user\'s query based on available data sources.',
  final_system_prompt:
    'Based on the provided context and the user\'s query, provide a clear helpful answer.',
  max_tokens: 1024,
  temperature: 0.7,
}

export type AgentInsertRowResponse = {
  answer?: string
  prompt?: string
  timestamp?: string
  doc_context?: unknown
  image_context?: unknown
  tool_output?: unknown
  [key: string]: unknown
}

/**
 * Replaces api.sendQuery(text, conversationId) only for "get an answer from agent row".
 * - Does NOT pass conversation_id (not an agent table column).
 * - Does NOT write chat_history — sidebar/conversations break unless you add calls or keep /api/agent/query.
 */
export async function sendQueryPxtRaw(
  prompt: string,
): Promise<AgentInsertRowResponse> {
  const body = {
    prompt,
    timestamp: new Date().toISOString(),
    initial_system_prompt: AGENT_DEFAULTS.initial_system_prompt,
    final_system_prompt: AGENT_DEFAULTS.final_system_prompt,
    max_tokens: AGENT_DEFAULTS.max_tokens,
    temperature: AGENT_DEFAULTS.temperature,
  }
  return requestJson<AgentInsertRowResponse>(`${PXT}/tables/agent/insert`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** Optional: map raw row to existing QueryMetadata + answer for minimal UI churn. */
export function toQueryResponseLike(row: AgentInsertRowResponse): {
  answer: string
  metadata: QueryMetadata
} {
  const ts = row.timestamp ?? new Date().toISOString()
  return {
    answer: String(row.answer ?? 'Error: No answer generated.'),
    metadata: {
      timestamp: typeof ts === 'string' ? ts : String(ts),
      has_doc_context: Boolean(row.doc_context),
      has_image_context: Boolean(row.image_context),
      has_tool_output: Boolean(row.tool_output),
    },
  }
}

// ── Background job (optional) ───────────────────────────────────────────────

export type JobPending = { id: string; job_url: string }
export type JobStatus =
  | { status: 'pending' }
  | { status: 'error'; error: string }
  | { status: 'done'; result: unknown }

export async function pollPxtJob(jobUrl: string): Promise<JobStatus> {
  return requestJson<JobStatus>(jobUrl, { method: 'GET' })
}

// ── Component diffs (illustrative) ───────────────────────────────────────────
//
// data-page.tsx — per file:
//   await uploadFilePxt(file, classifyMediaKind(file.name))
//
// search-page.tsx — swap:
//   const res = await searchPxt({ queryText: query.trim(), types: activeTypes, limit: 30 })
//
// agent-page.tsx — raw insert loses chat; realistic path is keep api.sendQuery OR:
//   const row = await sendQueryPxtRaw(trimmed)
//   const res = toQueryResponseLike(row)
//   // loadConversations() will NOT refresh unless backend still writes chat_history
