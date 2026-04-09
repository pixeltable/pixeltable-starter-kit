import { useState, useRef } from 'react'
import { flushSync } from 'react-dom'
import {
  Send, Loader2, Bot, User, Plus, Clock, Trash2,
  FileText, ImageIcon, Wrench,
} from 'lucide-react'
import { marked } from 'marked'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import * as api from '@/lib/api'
import { useMountEffect } from '@/lib/hooks'
import type { ChatMessage, Conversation, QueryMetadata } from '@/types'
import { cn } from '@/lib/utils'

export function AgentPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const loadConversations = async () => {
    try {
      const data = await api.getConversations()
      setConversations(data)
    } catch { /* empty */ }
  }

  useMountEffect(() => { loadConversations() })

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    flushSync(() => setMessages(prev => [...prev, userMsg]))
    scrollToBottom()
    setInput('')
    setIsLoading(true)

    const cid = conversationId ?? `conv_${Date.now()}`
    if (!conversationId) setConversationId(cid)

    try {
      const res = await api.sendQuery(trimmed, cid)
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: res.answer,
        metadata: res.metadata,
      }
      flushSync(() => setMessages(prev => [...prev, assistantMsg]))
      scrollToBottom()
      loadConversations()
    } catch (err) {
      const errMsg: ChatMessage = {
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Something went wrong'}`,
      }
      flushSync(() => setMessages(prev => [...prev, errMsg]))
      scrollToBottom()
    }
    setIsLoading(false)
    inputRef.current?.focus()
  }

  const startNewConversation = () => {
    setMessages([])
    setConversationId(null)
    setShowHistory(false)
    inputRef.current?.focus()
  }

  const loadConversation = async (id: string) => {
    try {
      const data = await api.getConversation(id)
      flushSync(() => setMessages(data.messages))
      scrollToBottom()
      setConversationId(id)
      setShowHistory(false)
    } catch { /* empty */ }
  }

  const handleDeleteConversation = async (id: string) => {
    try {
      await api.deleteConversation(id)
      if (conversationId === id) startNewConversation()
      loadConversations()
    } catch { /* empty */ }
  }

  return (
    <div className="flex h-full">
      {/* History sidebar */}
      <div
        className={cn(
          'border-r flex flex-col transition-all duration-200',
          showHistory ? 'w-64' : 'w-0 overflow-hidden',
        )}
      >
        <div className="flex items-center justify-between px-3 py-2 border-b">
          <span className="text-xs font-medium">Conversations</span>
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={startNewConversation}>
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="text-xs text-muted-foreground text-center py-6">No conversations yet</div>
          ) : (
            conversations.map(c => (
              <div
                key={c.conversation_id}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-accent transition-colors group',
                  conversationId === c.conversation_id && 'bg-accent',
                )}
                onClick={() => loadConversation(c.conversation_id)}
              >
                <div className="flex-1 min-w-0">
                  <div className="truncate">{c.title || 'Untitled'}</div>
                  <div className="text-muted-foreground">{c.message_count} messages</div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0"
                  onClick={e => { e.stopPropagation(); handleDeleteConversation(c.conversation_id) }}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b">
          <Button size="sm" variant="ghost" onClick={() => setShowHistory(h => !h)}>
            <Clock className="h-4 w-4 mr-1" />
            History
          </Button>
          <Button size="sm" variant="ghost" onClick={startNewConversation}>
            <Plus className="h-4 w-4 mr-1" />
            New
          </Button>
          <div className="flex-1" />
          <span className="text-xs text-muted-foreground">
            8-step tool-calling pipeline via Pixeltable computed columns
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Bot className="h-10 w-10 text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">
                Ask anything about your uploaded data
              </p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                The agent uses tool-calling, RAG retrieval, and multimodal context
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <MessageBubble key={`${msg.role}-${msg.timestamp ?? i}`} message={msg} />
          ))}
          {isLoading && (
            <div className="flex items-start gap-3">
              <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Processing through pipeline...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t p-4">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Ask about your data..."
              rows={1}
              className="flex-1 resize-none bg-card border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 max-h-32"
            />
            <Button onClick={handleSend} disabled={isLoading || !input.trim()}>
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex items-start gap-3', isUser && 'flex-row-reverse')}>
      <div
        className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0"
      >
        {isUser ? (
          <User className="h-4 w-4 text-primary" />
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>
      <div className={cn('max-w-[75%] min-w-0', isUser && 'text-right')}>
        {isUser ? (
          <div className="inline-block bg-primary text-primary-foreground rounded-lg rounded-tr-sm px-3 py-2 text-sm">
            {message.content}
          </div>
        ) : (
          <div className="bg-card border rounded-lg rounded-tl-sm px-3 py-2">
            <div
              className="prose-chat"
              dangerouslySetInnerHTML={{
                __html: marked.parse(message.content, { async: false }) as string,
              }}
            />
            {message.metadata && <MetadataBadges metadata={message.metadata} />}
          </div>
        )}
      </div>
    </div>
  )
}

function MetadataBadges({ metadata }: { metadata: QueryMetadata }) {
  return (
    <div className="flex items-center gap-1.5 mt-2 pt-2 border-t">
      {metadata.has_doc_context && (
        <Badge variant="blue">
          <FileText className="h-3 w-3 mr-0.5" /> Docs
        </Badge>
      )}
      {metadata.has_image_context && (
        <Badge variant="green">
          <ImageIcon className="h-3 w-3 mr-0.5" /> Images
        </Badge>
      )}
      {metadata.has_tool_output && (
        <Badge variant="orange">
          <Wrench className="h-3 w-3 mr-0.5" /> Tools
        </Badge>
      )}
    </div>
  )
}
