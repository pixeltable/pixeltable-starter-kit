import { useState } from 'react'
import { Search as SearchIcon, Loader2, FileText, ImageIcon, Film, AudioLines } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import * as api from '@/lib/api'
import type { SearchResult } from '@/types'
import { cn, toDataUrl } from '@/lib/utils'

const TYPE_CONFIG = {
  document: { label: 'Document', icon: FileText, badge: 'blue' as const, color: 'text-blue-500' },
  image: { label: 'Image', icon: ImageIcon, badge: 'green' as const, color: 'text-emerald-500' },
  video_frame: { label: 'Video Frame', icon: Film, badge: 'purple' as const, color: 'text-purple-500' },
  transcript: { label: 'Transcript', icon: AudioLines, badge: 'yellow' as const, color: 'text-yellow-600' },
} as const

const ALL_TYPES = Object.keys(TYPE_CONFIG) as Array<keyof typeof TYPE_CONFIG>

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set(ALL_TYPES))

  const toggleType = (type: string) => {
    setActiveTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const handleSearch = async () => {
    if (!query.trim()) return
    setIsSearching(true)
    setHasSearched(true)
    try {
      const res = await api.search({
        query: query.trim(),
        types: Array.from(activeTypes),
        limit: 30,
      })
      setResults(res.results)
    } catch (err) {
      console.error('Search failed:', err)
    }
    setIsSearching(false)
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Search bar */}
      <div className="p-4 space-y-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Semantic search across all your data..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              className="w-full pl-10 pr-4 py-2 bg-card border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <Button onClick={handleSearch} disabled={isSearching || !query.trim()}>
            {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Search'}
          </Button>
        </div>

        {/* Type filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground">Search across:</span>
          {ALL_TYPES.map(type => {
            const cfg = TYPE_CONFIG[type]
            const Icon = cfg.icon
            const active = activeTypes.has(type)
            return (
              <button
                key={type}
                onClick={() => toggleType(type)}
                className={cn(
                  'flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer border',
                  active
                    ? 'bg-accent text-foreground border-border'
                    : 'text-muted-foreground border-transparent opacity-50 hover:opacity-75',
                )}
              >
                <Icon className={cn('h-3 w-3', active && cfg.color)} />
                {cfg.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 px-4 pb-4">
        {!hasSearched ? (
          <EmptyState />
        ) : isSearching ? (
          <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Searching with embedding indexes...
          </div>
        ) : results.length === 0 ? (
          <div className="text-center text-muted-foreground text-sm py-12">
            No results found for "{query}"
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-xs text-muted-foreground mb-2">
              {results.length} result{results.length !== 1 ? 's' : ''} — ranked by embedding similarity
            </div>
            {results.map((r, i) => (
              <ResultCard key={`${r.uuid}-${i}`} result={r} rank={i + 1} />
            ))}
          </div>
        )}
      </div>

      {/* Pipeline info */}
      <div className="border-t px-4 py-2 text-xs text-muted-foreground flex items-center gap-4">
        <span>Text: sentence-transformer embedding</span>
        <span>Images + Frames: CLIP embedding</span>
        <span>All powered by pxt.similarity()</span>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <SearchIcon className="h-10 w-10 text-muted-foreground/40 mb-3" />
      <p className="text-sm text-muted-foreground">
        Search across documents, images, video frames, and transcriptions
      </p>
      <p className="text-xs text-muted-foreground/70 mt-1">
        Uses Pixeltable embedding indexes for cross-modal semantic search
      </p>
    </div>
  )
}

function ResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const cfg = TYPE_CONFIG[result.type]
  const Icon = cfg.icon

  return (
    <div className="border rounded-lg p-3 hover:bg-accent/30 transition-colors">
      <div className="flex items-start gap-3">
        <span className="text-xs text-muted-foreground mt-0.5 w-5 text-right shrink-0">
          {rank}
        </span>
        <Icon className={cn('h-4 w-4 mt-0.5 shrink-0', cfg.color)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant={cfg.badge}>{cfg.label}</Badge>
            <span className="text-xs text-muted-foreground">
              {(result.similarity * 100).toFixed(0)}% match
            </span>
            {result.metadata?.source ? (
              <span className="text-xs text-muted-foreground truncate">
                {String(result.metadata.source)}
              </span>
            ) : null}
          </div>

          {result.text && (
            <p className="text-sm line-clamp-3">{result.text}</p>
          )}

          {result.thumbnail && (
            <img
              src={toDataUrl(result.thumbnail)}
              alt="Result thumbnail"
              className="mt-1 h-24 rounded border"
            />
          )}
        </div>

        <div className="shrink-0">
          <div
            className="h-2 rounded-full bg-primary/20"
            style={{ width: `${Math.round(result.similarity * 60)}px` }}
          >
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${result.similarity * 100}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
