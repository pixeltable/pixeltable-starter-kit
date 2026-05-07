export interface QueryMetadata {
  timestamp: string
  has_doc_context: boolean
  has_image_context: boolean
  has_tool_output: boolean
}

export interface QueryResponse {
  answer: string
  metadata: QueryMetadata
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  metadata?: QueryMetadata
}

export interface Conversation {
  conversation_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface FileItem {
  uuid: string
  name: string
  thumbnail?: string | null
  timestamp?: string | null
}

export interface FilesResponse {
  documents: FileItem[]
  images: FileItem[]
  videos: FileItem[]
}

export interface ChunkItem {
  text: string
  title?: string
  heading?: Record<string, string>
  page?: number
}

export interface FrameItem {
  frame: string
  position: number
}

export interface PxtQueryResponse<T> {
  rows: T[]
}

export interface SearchResult {
  type: 'document' | 'image' | 'video_frame' | 'transcript'
  uuid: string
  similarity: number
  text?: string
  thumbnail?: string | null
  metadata?: Record<string, unknown>
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
}
