'use client'

import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Bot, X } from 'lucide-react'
import ChatWindow from './ChatWindow'
import ChatInput from './ChatInput'
import { cn } from '@/lib/utils'
import { listAgents } from '@/lib/api'
import type { Message, Session, ToolCall, Agent } from '@/lib/types'

interface ChatMainProps {
  sessions: Session[]
  activeSessionId: string | null
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
  toolCalls: ToolCall[]
  isLoadingMessages: boolean
  isConnected: boolean
  selectedAgentId: string | null
  onSelectAgent: (id: string | null) => void
  sendChatMessage: (message: string) => void
  stopGeneration: () => void
  messagesEndRef: React.RefObject<HTMLDivElement>
}

function AgentSelector({
  selectedAgentId,
  onSelectAgent,
}: {
  selectedAgentId: string | null
  onSelectAgent: (id: string | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const selected = agents.find((a) => a.id === selectedAgentId)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    listAgents()
      .then(setAgents)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open])

  // Refresh agent list when the selected agent changes so the button label stays current
  useEffect(() => {
    if (!selectedAgentId) return
    listAgents()
      .then(setAgents)
      .catch(() => {})
  }, [selectedAgentId])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm transition-all',
          selected
            ? 'bg-white/[0.08] text-white border border-white/10'
            : 'text-white/50 hover:text-white hover:bg-white/[0.05]'
        )}
      >
        {selected ? (
          <>
            <span className="text-sm leading-none">
              {(selected.meta?.avatar_emoji as string) || '🤖'}
            </span>
            <span className="font-medium text-xs max-w-[120px] truncate">{selected.name}</span>
          </>
        ) : (
          <>
            <Bot size={13} className="text-white/40" />
            <span className="text-xs">Default</span>
          </>
        )}
        <ChevronDown size={11} className="text-white/30 ml-0.5" />
      </button>

      {/* Clear selected agent */}
      {selected && (
        <button
          onClick={() => onSelectAgent(null)}
          className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[#1a1a1a] border border-white/10 flex items-center justify-center text-white/40 hover:text-white/70 transition-colors"
        >
          <X size={8} />
        </button>
      )}

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 top-full mt-1.5 w-64 bg-[#161616] border border-white/[0.08] rounded-xl shadow-2xl overflow-hidden z-50">
          <div className="px-3 py-2 border-b border-white/[0.06]">
            <p className="text-[11px] text-white/30 font-medium">Select Agent</p>
          </div>

          {/* Default option */}
          <button
            onClick={() => { onSelectAgent(null); setOpen(false) }}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors',
              !selectedAgentId ? 'bg-white/[0.06]' : 'hover:bg-white/[0.04]'
            )}
          >
            <div className="w-7 h-7 rounded-lg bg-white/[0.06] flex items-center justify-center flex-shrink-0">
              <Bot size={13} className="text-white/40" />
            </div>
            <div>
              <p className="text-sm text-white font-medium">Default (Yuno)</p>
              <p className="text-[11px] text-white/30">General-purpose assistant</p>
            </div>
          </button>

          <div className="max-h-56 overflow-y-auto">
            {loading ? (
              <div className="px-4 py-3 text-xs text-white/30">Loading agents…</div>
            ) : agents.length === 0 ? (
              <div className="px-4 py-3 text-xs text-white/30">No agents created yet</div>
            ) : (
              agents.map((agent) => {
                const emoji = (agent.meta?.avatar_emoji as string) || '🤖'
                return (
                  <button
                    key={agent.id}
                    onClick={() => { onSelectAgent(agent.id); setOpen(false) }}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors',
                      selectedAgentId === agent.id ? 'bg-white/[0.06]' : 'hover:bg-white/[0.04]'
                    )}
                  >
                    <div className="w-7 h-7 rounded-lg bg-white/[0.06] flex items-center justify-center text-base flex-shrink-0">
                      {emoji}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-white font-medium truncate">{agent.name}</p>
                      <p className="text-[11px] text-white/30 capitalize truncate">{agent.role} · {agent.model.split('-').slice(0, 2).join('-')}</p>
                    </div>
                    {selectedAgentId === agent.id && (
                      <div className="w-1.5 h-1.5 rounded-full bg-white/60 flex-shrink-0" />
                    )}
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ChatMain({
  sessions,
  activeSessionId,
  messages,
  isStreaming,
  streamingContent,
  toolCalls,
  isLoadingMessages,
  isConnected,
  selectedAgentId,
  onSelectAgent,
  sendChatMessage,
  stopGeneration,
  messagesEndRef,
}: ChatMainProps) {
  const hasMessages = messages.length > 0 || (isStreaming && !!streamingContent) || toolCalls.length > 0

  return (
    <main className="flex-1 flex flex-col h-full min-w-0 bg-[#0d0d0d]">
      {/* Top bar */}
      <header className="flex items-center justify-between px-5 py-3 flex-shrink-0 h-12">
        <AgentSelector selectedAgentId={selectedAgentId} onSelectAgent={onSelectAgent} />

        <div
          className={cn(
            'w-2 h-2 rounded-full transition-colors duration-1000',
            isConnected ? 'bg-emerald-500/50' : 'bg-red-500/50'
          )}
          title={isConnected ? 'Connected' : 'Reconnecting…'}
        />
      </header>

      {/* Message/welcome area */}
      <ChatWindow
        messages={messages}
        isStreaming={isStreaming}
        streamingContent={streamingContent}
        toolCalls={toolCalls}
        isLoadingMessages={isLoadingMessages}
        messagesEndRef={messagesEndRef}
        onSuggestionClick={sendChatMessage}
        onSend={sendChatMessage}
        onStop={stopGeneration}
        isConnected={isConnected}
      />

      {/* Bottom input */}
      {hasMessages && (
        <ChatInput
          onSend={sendChatMessage}
          onStop={stopGeneration}
          isStreaming={isStreaming}
          isConnected={isConnected}
        />
      )}
    </main>
  )
}
