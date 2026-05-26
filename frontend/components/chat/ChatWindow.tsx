'use client'

import { useEffect, useRef } from 'react'
import { ImageIcon, PenLine, Globe, AlertTriangle } from 'lucide-react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import ToolCallBubble from './ToolCallBubble'
import { useChatStore } from '@/store/chatStore'
import { useSmoothedText } from '@/hooks/useSmoothedText'
import type { Message, ToolCall } from '@/lib/types'

// Renders the streaming response through the smoothing buffer so chunks
// appear as continuous typing rather than irregular network-sized bursts.
function StreamingMessage({
  content,
  isStreaming,
}: {
  content: string
  isStreaming: boolean
}) {
  const smoothed = useSmoothedText(content, isStreaming)
  return (
    <ChatMessage
      message={{ session_id: '', role: 'assistant', content: smoothed }}
      isLast={true}
      isStreaming={true}
    />
  )
}

interface ChatWindowProps {
  messages: Message[]
  isStreaming: boolean
  streamingContent: string
  toolCalls: ToolCall[]
  isLoadingMessages: boolean
  messagesEndRef: React.RefObject<HTMLDivElement>
  onSuggestionClick: (prompt: string) => void
  onSend: (message: string) => void
  onStop?: () => void
  isConnected: boolean
}

const SUGGESTIONS = [
  {
    icon: <ImageIcon size={13} />,
    title: 'Create an image',
    prompt: 'Create a detailed image prompt for a serene mountain landscape at golden hour.',
  },
  {
    icon: <PenLine size={13} />,
    title: 'Write or edit',
    prompt: 'Help me write a concise, professional bio for my portfolio.',
  },
  {
    icon: <Globe size={13} />,
    title: 'Look something up',
    prompt: 'What are the key differences between REST and GraphQL APIs?',
  },
]

function WelcomeScreen({
  onSuggestionClick,
  onSend,
  onStop,
  isStreaming,
  isConnected,
}: {
  onSuggestionClick: (prompt: string) => void
  onSend: (message: string) => void
  onStop?: () => void
  isStreaming: boolean
  isConnected: boolean
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 pb-14 animate-[fade-in_0.15s_ease-out]">
      <h2 className="text-[1.8rem] font-semibold text-white mb-7 tracking-tight">
        What are you working on?
      </h2>

      <div className="w-full max-w-[44rem] space-y-3">
        <ChatInput
          onSend={onSend}
          onStop={onStop}
          isStreaming={isStreaming}
          isConnected={isConnected}
          variant="pill"
        />

        <div className="flex items-center justify-center gap-2 flex-wrap pt-0.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s.title}
              onClick={() => onSuggestionClick(s.prompt)}
              className="flex items-center gap-2 px-4 py-2 rounded-full border border-white/[0.12] text-[#b0b0b0] hover:text-white hover:border-white/[0.22] hover:bg-white/[0.04] text-[13px] transition-all duration-150"
            >
              <span className="text-white/40">{s.icon}</span>
              {s.title}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function LoadingMessages() {
  return (
    <div className="flex-1 flex flex-col gap-6 px-6 py-6 max-w-3xl mx-auto w-full">
      {[1, 2, 3].map((i) => (
        <div key={i} className={`flex gap-3 ${i % 2 === 0 ? 'flex-row-reverse' : ''}`}>
          <div className="skeleton w-7 h-7 rounded-full flex-shrink-0" />
          <div className={`flex flex-col gap-2 max-w-md ${i % 2 === 0 ? 'items-end' : ''}`}>
            <div className="skeleton h-3 w-48 rounded" />
            <div className="skeleton h-3 w-64 rounded" />
            <div className="skeleton h-3 w-36 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function ChatWindow({
  messages,
  isStreaming,
  streamingContent,
  toolCalls,
  isLoadingMessages,
  messagesEndRef,
  onSuggestionClick,
  onSend,
  onStop,
  isConnected,
}: ChatWindowProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const providerFallback = useChatStore((s) => s.providerFallback)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const { scrollTop, scrollHeight, clientHeight } = container
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 200
    if (isNearBottom || isStreaming) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages, streamingContent, isStreaming])

  if (isLoadingMessages) {
    return (
      <div className="flex-1 overflow-y-auto min-h-0">
        <LoadingMessages />
      </div>
    )
  }

  const hasMessages = messages.length > 0 || (isStreaming && !!streamingContent)

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto min-h-0 scroll-smooth"
    >
      {!hasMessages ? (
        <WelcomeScreen
          onSuggestionClick={onSuggestionClick}
          onSend={onSend}
          onStop={onStop}
          isStreaming={isStreaming}
          isConnected={isConnected}
        />
      ) : (
        <div className="flex flex-col gap-0.5 px-4 py-6 max-w-3xl mx-auto w-full">
          {messages.map((message, index) => {
            if (message.role === 'tool') {
              try {
                const data = JSON.parse(message.content)
                const call: ToolCall = {
                  id: message.id || `tool-${index}`,
                  tool_name: data.tool_name,
                  tool_input: data.tool_input ?? {},
                  tool_result: data.tool_result,
                  status: data.status ?? 'done',
                  started_at: message.created_at || new Date().toISOString(),
                }
                return <ToolCallBubble key={message.id || `tool-${index}`} call={call} />
              } catch {
                return null
              }
            }
            return (
              <ChatMessage
                key={message.id || `msg-${index}`}
                message={message}
                isLast={index === messages.length - 1}
              />
            )
          })}

          {/* Live tool calls during active streaming */}
          {toolCalls.map((call) => (
            <ToolCallBubble key={call.id} call={call} />
          ))}

          {/* Provider fallback nudge — ephemeral, shown only during active streaming */}
          {isStreaming && providerFallback && (
            <div className="flex items-start gap-3 py-1.5 animate-[fade-in_0.2s_ease-out]">
              <div className="w-7 h-7 flex-shrink-0" />
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[12px] text-amber-400/80">
                <AlertTriangle size={12} className="shrink-0" />
                <span>
                  <span className="font-medium capitalize">{providerFallback.from}</span>
                  {' unavailable — trying '}
                  <span className="font-medium capitalize">{providerFallback.to}</span>
                </span>
              </div>
            </div>
          )}

          {isStreaming && streamingContent && (
            <StreamingMessage content={streamingContent} isStreaming={isStreaming} />
          )}

          {/* Thinking dots — only shown while waiting (no chunks and no tool calls yet) */}
          {isStreaming && !streamingContent && toolCalls.length === 0 && (
            <div className="flex items-start gap-3 py-2 animate-[fade-in_0.2s_ease-out]">
              <div className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-white text-[10px] font-bold">O</span>
              </div>
              <div className="flex items-center gap-1.5 py-2.5 px-3.5 rounded-2xl rounded-tl-sm bg-[#1f1f1f]">
                <span className="w-1.5 h-1.5 rounded-full bg-white/50 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-white/50 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-white/50 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} className="h-4" />
        </div>
      )}
    </div>
  )
}
