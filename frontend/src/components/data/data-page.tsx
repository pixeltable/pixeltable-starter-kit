import { useState, useRef } from 'react'
import {
  Upload, FileText, ImageIcon, Video, Trash2, ChevronDown, ChevronUp,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import * as api from '@/lib/api'
import { useMountEffect } from '@/lib/hooks'
import type { FileItem, ChunkItem, FrameItem } from '@/types'
import { cn, toDataUrl } from '@/lib/utils'

type MediaTab = 'documents' | 'images' | 'videos'

export function DataPage() {
  const [tab, setTab] = useState<MediaTab>('documents')
  const [files, setFiles] = useState<{
    documents: FileItem[]
    images: FileItem[]
    videos: FileItem[]
  }>({ documents: [], images: [], videos: [] })
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('')
  const [expandedUuid, setExpandedUuid] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadFiles = async () => {
    try {
      const data = await api.getFiles()
      setFiles(data)
    } catch { /* empty */ }
  }

  useMountEffect(() => { loadFiles() })

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList?.length) return
    setIsUploading(true)
    try {
      for (const file of Array.from(fileList)) {
        setUploadStatus(`Uploading ${file.name}…`)
        const result = await api.uploadFile(file)
        if (result.jobPath) {
          setUploadStatus(`Processing ${file.name}…`)
          await api.pollJob(result.jobPath)
        }
      }
      await loadFiles()
    } catch (err) {
      console.error('Upload failed:', err)
    } finally {
      setIsUploading(false)
      setUploadStatus('')
    }
  }

  const handleDelete = async (uuid: string, type: string) => {
    try {
      await api.deleteFile(uuid, type)
      await loadFiles()
      if (expandedUuid === uuid) setExpandedUuid(null)
    } catch { /* empty */ }
  }

  const currentFiles = files[tab]
  const typeForDelete = tab === 'documents' ? 'document' : tab === 'images' ? 'image' : 'video'

  const counts = {
    documents: files.documents.length,
    images: files.images.length,
    videos: files.videos.length,
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Upload zone */}
      <div
        className="m-4 mb-2 border-2 border-dashed rounded-lg p-6 text-center hover:border-primary/50 transition-colors cursor-pointer"
        onDragOver={e => { e.preventDefault(); e.stopPropagation() }}
        onDrop={e => { e.preventDefault(); e.stopPropagation(); handleUpload(e.dataTransfer.files) }}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={e => handleUpload(e.target.files)}
        />
        {isUploading ? (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            {uploadStatus || 'Uploading…'}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1 text-muted-foreground">
            <Upload className="h-6 w-6" />
            <span className="text-sm">Drop files here or click to upload</span>
            <span className="text-xs">Documents, images, or videos</span>
          </div>
        )}
      </div>

      {/* Type tabs */}
      <div className="flex items-center gap-1 px-4 py-2">
        {([
          { key: 'documents' as const, label: 'Documents', icon: FileText },
          { key: 'images' as const, label: 'Images', icon: ImageIcon },
          { key: 'videos' as const, label: 'Videos', icon: Video },
        ]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setTab(key); setExpandedUuid(null) }}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer',
              tab === key
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-accent',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
            {counts[key] > 0 && (
              <span className={cn(
                'ml-1 text-xs rounded-full px-1.5 py-0.5',
                tab === key ? 'bg-primary-foreground/20' : 'bg-muted',
              )}>
                {counts[key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* File list */}
      <div className="flex-1 px-4 pb-4">
        {currentFiles.length === 0 ? (
          <div className="text-center text-muted-foreground text-sm py-12">
            No {tab} uploaded yet
          </div>
        ) : tab === 'images' ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {currentFiles.map(f => (
              <ImageCard
                key={f.uuid}
                file={f}
                onDelete={() => handleDelete(f.uuid, 'image')}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-1">
            {currentFiles.map(f => (
              <FileRow
                key={f.uuid}
                file={f}
                type={typeForDelete}
                isExpanded={expandedUuid === f.uuid}
                onToggle={() => setExpandedUuid(expandedUuid === f.uuid ? null : f.uuid)}
                onDelete={() => handleDelete(f.uuid, typeForDelete)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pipeline info */}
      <div className="border-t px-4 py-2 text-xs text-muted-foreground flex items-center gap-4">
        <span>Pixeltable tables: app.documents, app.images, app.videos</span>
        <span>Views: app.chunks, app.video_frames, app.video_sentences</span>
        <span>Total files: {counts.documents + counts.images + counts.videos}</span>
      </div>
    </div>
  )
}

// ── File row (documents & videos) ────────────────────────────────────────────

function FileRow({ file, type, isExpanded, onToggle, onDelete }: {
  file: FileItem
  type: string
  isExpanded: boolean
  onToggle: () => void
  onDelete: () => void
}) {
  return (
    <div className="border rounded-lg">
      <div
        className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-accent/50 transition-colors"
        onClick={onToggle}
      >
        {isExpanded ? <ChevronUp className="h-4 w-4 shrink-0" /> : <ChevronDown className="h-4 w-4 shrink-0" />}
        {type === 'document' ? <FileText className="h-4 w-4 shrink-0 text-blue-500" /> : <Video className="h-4 w-4 shrink-0 text-purple-500" />}
        <span className="text-sm truncate flex-1">{file.name}</span>
        <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={e => { e.stopPropagation(); onDelete() }}>
          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
      </div>
      {isExpanded && (
        <div className="border-t px-4 py-3">
          {type === 'document' ? (
            <DocumentDetail uuid={file.uuid} />
          ) : (
            <VideoDetail uuid={file.uuid} />
          )}
        </div>
      )}
    </div>
  )
}

// ── Document detail (chunks) ─────────────────────────────────────────────────

function DocumentDetail({ uuid }: { uuid: string }) {
  const [chunks, setChunks] = useState<ChunkItem[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useMountEffect(() => {
    setIsLoading(true)
    api.getChunks(uuid)
      .then(data => setChunks(data.rows))
      .catch(() => {})
      .finally(() => setIsLoading(false))
  })

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading chunks...</div>
  if (!chunks.length) return <div className="text-sm text-muted-foreground">No chunks extracted yet</div>

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-muted-foreground">
        {chunks.length} chunks from DocumentSplitter
      </div>
      <div className="max-h-64 overflow-y-auto space-y-2">
        {chunks.map((c, i) => (
          <div key={i} className="text-xs bg-muted rounded p-2">
            {c.page != null && <Badge variant="blue" className="mr-1">p.{c.page}</Badge>}
            {c.text}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Image card ───────────────────────────────────────────────────────────────

function ImageCard({ file, onDelete }: {
  file: FileItem
  onDelete: () => void
}) {
  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="relative group">
        {file.thumbnail ? (
          <img src={toDataUrl(file.thumbnail)} alt={file.name} className="w-full aspect-square object-cover" />
        ) : (
          <div className="w-full aspect-square bg-muted flex items-center justify-center">
            <ImageIcon className="h-8 w-8 text-muted-foreground" />
          </div>
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 opacity-0 group-hover:opacity-100 text-white bg-black/40"
            onClick={onDelete}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <div className="px-2 py-1.5 text-xs truncate text-muted-foreground">{file.name}</div>
    </div>
  )
}

// ── Video detail (frames + transcription) ────────────────────────────────────

function VideoDetail({ uuid }: { uuid: string }) {
  const [frames, setFrames] = useState<FrameItem[]>([])
  const [transcription, setTranscription] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)

  useMountEffect(() => {
    setIsLoading(true)
    Promise.all([
      api.getFrames(uuid).catch(() => ({ rows: [] })),
      api.getTranscription(uuid).catch(() => ({ rows: [] })),
    ]).then(([f, t]) => {
      setFrames(f.rows ?? [])
      const seen = new Set<string>()
      const texts: string[] = []
      for (const row of t.rows ?? []) {
        if (row.text && !seen.has(row.text)) {
          seen.add(row.text)
          texts.push(row.text)
        }
      }
      setTranscription(texts.join(' '))
    }).finally(() => setIsLoading(false))
  })

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading video data...</div>

  return (
    <div className="space-y-3">
      {frames.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">
            Keyframes ({frames.length}) — from FrameIterator
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
            {frames.map((f, i) => (
              <img
                key={i}
                src={toDataUrl(f.frame)}
                alt={`Frame ${i}`}
                className="w-full aspect-video object-cover rounded border"
              />
            ))}
          </div>
        </div>
      )}
      {transcription && (
        <div>
          <div className="text-xs font-medium text-muted-foreground mb-1">
            Transcription — Whisper + StringSplitter
          </div>
          <div className="text-xs bg-muted rounded p-2 max-h-32 overflow-y-auto">
            {transcription}
          </div>
        </div>
      )}
      {!frames.length && !transcription && (
        <div className="text-sm text-muted-foreground">Processing... check back shortly</div>
      )}
    </div>
  )
}
