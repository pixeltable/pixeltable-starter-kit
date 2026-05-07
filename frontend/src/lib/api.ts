import type {
  QueryResponse, FilesResponse, FileItem, PxtQueryResponse,
  ChunkItem, FrameItem, SearchResponse, SearchResult, Conversation, ChatMessage,
} from '@/types'

const BASE = '/api'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail ?? body.error ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

function basename(path: string): string {
  return path.split('/').pop() ?? path
}

// ── Data ─────────────────────────────────────────────────────────────────────

const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff'])
const VIDEO_EXTS = new Set(['.mp4', '.mov', '.avi', '.webm', '.mkv'])
type MediaType = 'document' | 'image' | 'video'

function classifyFile(filename: string): MediaType {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase()
  if (IMAGE_EXTS.has(ext)) return 'image'
  if (VIDEO_EXTS.has(ext)) return 'video'
  return 'document'
}

export interface UploadResult { uuid?: string; thumbnail?: string; jobPath?: string }

export async function uploadFile(file: File): Promise<UploadResult> {
  const mediaType = classifyFile(file.name)
  const formData = new FormData()
  formData.append(mediaType, file)
  formData.append('timestamp', new Date().toISOString())

  const res = await fetch(`${BASE}/data/upload/${mediaType}`, { method: 'POST', body: formData })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail ?? `HTTP ${res.status}`)
  }
  const data = await res.json()
  if (data.job_url) return { jobPath: new URL(data.job_url).pathname }
  return data
}

export async function pollJob(jobPath: string): Promise<Record<string, unknown>> {
  for (;;) {
    await new Promise((r) => setTimeout(r, 1500))
    const res = await request<{ status: string; result?: Record<string, unknown>; error?: string }>(jobPath)
    if (res.status === 'done') return res.result ?? {}
    if (res.status === 'error') throw new Error(res.error ?? 'Processing failed')
  }
}

export async function deleteFile(uuid: string, type: string) {
  return request<{ num_rows: number }>(`${BASE}/data/delete/${type}`, {
    method: 'POST', body: JSON.stringify({ uuid }),
  })
}

function toFileItem(row: Record<string, unknown>): FileItem {
  return {
    uuid: String(row.uuid ?? ''),
    name: basename(String(row.name ?? '')),
    thumbnail: (row.thumbnail as string) ?? null,
    timestamp: row.timestamp != null ? String(row.timestamp) : null,
  }
}

export async function getFiles(): Promise<FilesResponse> {
  const [docs, imgs, vids] = await Promise.all([
    request<PxtQueryResponse<Record<string, unknown>>>(`${BASE}/data/list/documents`),
    request<PxtQueryResponse<Record<string, unknown>>>(`${BASE}/data/list/images`),
    request<PxtQueryResponse<Record<string, unknown>>>(`${BASE}/data/list/videos`),
  ])
  return {
    documents: (docs.rows ?? []).map(toFileItem),
    images: (imgs.rows ?? []).map(toFileItem),
    videos: (vids.rows ?? []).map(toFileItem),
  }
}

export async function getChunks(uuid: string): Promise<PxtQueryResponse<ChunkItem>> {
  return request(`${BASE}/data/chunks`, { method: 'POST', body: JSON.stringify({ file_uuid: uuid }) })
}

export async function getFrames(uuid: string): Promise<PxtQueryResponse<FrameItem>> {
  return request(`${BASE}/data/frames`, { method: 'POST', body: JSON.stringify({ file_uuid: uuid }) })
}

export async function getTranscription(uuid: string): Promise<PxtQueryResponse<{ text: string }>> {
  return request(`${BASE}/data/transcription`, { method: 'POST', body: JSON.stringify({ file_uuid: uuid }) })
}

// ── Search ───────────────────────────────────────────────────────────────────

function toSearchResult(type: SearchResult['type'], r: Record<string, unknown>): SearchResult {
  return {
    type,
    uuid: String(r.uuid ?? ''),
    similarity: Number(r.sim ?? 0),
    text: r.text as string | undefined,
    thumbnail: r.thumbnail as string | undefined,
    metadata: { source: basename(String(r.source ?? '')), ...(r.title ? { title: r.title } : {}) },
  }
}

const SEARCH_ENDPOINTS: Array<{ type: SearchResult['type']; path: string }> = [
  { type: 'document', path: '/search/documents' },
  { type: 'image', path: '/search/images' },
  { type: 'video_frame', path: '/search/video-frames' },
  { type: 'transcript', path: '/search/transcripts' },
]

export async function search(params: { query: string; types?: string[]; limit?: number }): Promise<SearchResponse> {
  const types = new Set(params.types ?? SEARCH_ENDPOINTS.map((e) => e.type))
  const limit = params.limit ?? 30

  const calls = SEARCH_ENDPOINTS.filter((e) => types.has(e.type)).map(async ({ type, path }) => {
    try {
      const res = await request<PxtQueryResponse<Record<string, unknown>>>(
        `${BASE}${path}`, { method: 'POST', body: JSON.stringify({ query_text: params.query }) },
      )
      const rows = (res.rows ?? []).map((r) => toSearchResult(type, r))
      if (type === 'transcript') {
        const seen = new Set<string>()
        return rows.filter((r) => r.text && !seen.has(r.text) && seen.add(r.text))
      }
      return rows
    } catch { return [] }
  })

  const allResults = (await Promise.all(calls)).flat()
  allResults.sort((a, b) => b.similarity - a.similarity)
  return { query: params.query, results: allResults.slice(0, limit) }
}

// ── Agent ────────────────────────────────────────────────────────────────────

export async function sendQuery(query: string, conversationId?: string | null): Promise<QueryResponse> {
  return request<QueryResponse>(`${BASE}/agent/query`, {
    method: 'POST', body: JSON.stringify({ query, conversation_id: conversationId }),
  })
}

export async function getConversations(): Promise<Conversation[]> {
  const data = await request<PxtQueryResponse<Record<string, unknown>>>(`${BASE}/agent/messages`)
  const convos = new Map<string, Conversation>()

  for (const row of data.rows ?? []) {
    const cid = String(row.conversation_id || 'default')
    const ts = String(row.timestamp ?? '')
    if (!convos.has(cid)) {
      convos.set(cid, { conversation_id: cid, title: '', created_at: ts, updated_at: ts, message_count: 0 })
    }
    const entry = convos.get(cid)!
    entry.message_count += 1
    entry.updated_at = ts
    if (!entry.title && row.role === 'user') entry.title = String(row.content ?? '').slice(0, 100)
  }
  return [...convos.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}

export async function getConversation(id: string): Promise<PxtQueryResponse<ChatMessage>> {
  return request(`${BASE}/agent/conversation`, { method: 'POST', body: JSON.stringify({ conversation_id: id }) })
}

export async function deleteConversation(id: string) {
  return request<{ num_rows: number }>(`${BASE}/agent/delete-conversation`, {
    method: 'POST', body: JSON.stringify({ conversation_id: id }),
  })
}
