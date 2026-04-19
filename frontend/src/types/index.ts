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
  // Pixeltable's DocumentSplitter returns heading as a map, e.g. { h1: "...", h2: "..." }
  heading?: Record<string, string>
  page?: number
}

export interface ChunksResponse {
  uuid: string
  chunks: ChunkItem[]
  total: number
}

export interface FrameItem {
  frame: string
  position: number
}

export interface FramesResponse {
  uuid: string
  frames: FrameItem[]
  total: number
}

export interface TranscriptionResponse {
  uuid: string
  sentences: string[]
  full_text: string
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
