import { useState } from 'react'
import { Database, Search, Bot, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DataPage } from '@/components/data/data-page'
import { SearchPage } from '@/components/search/search-page'
import { AgentPage } from '@/components/agent/agent-page'

const TABS = [
  { id: 'data', label: 'Data', icon: Database },
  { id: 'search', label: 'Search', icon: Search },
  { id: 'agent', label: 'Agent', icon: Bot },
] as const

type TabId = (typeof TABS)[number]['id']

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>('data')

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between border-b px-6 h-14 shrink-0">
        <div className="flex items-center gap-6">
          <h1 className="text-base font-semibold tracking-tight">
            Pixeltable Starter Kit
          </h1>

          <nav className="flex items-center gap-1 bg-muted rounded-lg p-1">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={cn(
                  'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer',
                  activeTab === id
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </nav>
        </div>

        <a
          href="https://docs.pixeltable.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Pixeltable Docs
          <ExternalLink className="h-3 w-3" />
        </a>
      </header>

      <main className="flex-1 overflow-hidden">
        {activeTab === 'data' && <DataPage />}
        {activeTab === 'search' && <SearchPage />}
        {activeTab === 'agent' && <AgentPage />}
      </main>
    </div>
  )
}
