'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import type { Message } from '@/lib/types'

interface ChatMessageProps {
  message: Message
  isLast?: boolean
  isStreaming?: boolean
}

export default function ChatMessage({ message, isLast, isStreaming = false }: ChatMessageProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end py-1 animate-[fade-in_0.15s_ease-out]">
        <div
          className={cn(
            'max-w-[78%] px-4 py-3 rounded-3xl rounded-br-lg',
            'bg-[#2f2f2f] text-white text-sm leading-relaxed',
            'whitespace-pre-wrap break-words'
          )}
        >
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 py-1 animate-[fade-in_0.15s_ease-out]">
      <div className="w-7 h-7 rounded-full bg-white/[0.08] flex items-center justify-center flex-shrink-0 mt-0.5">
        <span className="text-white text-[10px] font-bold">O</span>
      </div>

      <div className="flex-1 min-w-0 pt-0.5 pb-1">
        <div
          className={cn(
            'text-sm leading-relaxed',
            isStreaming && isLast ? 'streaming-cursor' : ''
          )}
        >
          <div className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  )
}
