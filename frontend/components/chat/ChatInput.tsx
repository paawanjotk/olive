'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { Plus, ArrowUp, Mic, Square } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChatInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  isStreaming: boolean
  isConnected: boolean
  variant?: 'bar' | 'pill'
}

export default function ChatInput({
  onSend,
  onStop,
  isStreaming,
  isConnected,
  variant = 'bar',
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const MAX_ROWS = 5
  const LINE_HEIGHT = 24
  const BASE_HEIGHT = 24

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const scrollHeight = el.scrollHeight
    const maxHeight = LINE_HEIGHT * MAX_ROWS
    el.style.height = `${Math.min(scrollHeight, maxHeight)}px`
    el.style.overflowY = scrollHeight > maxHeight ? 'auto' : 'hidden'
  }, [])

  useEffect(() => {
    adjustHeight()
  }, [value, adjustHeight])

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming || !isConnected) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = `${BASE_HEIGHT}px`
    }
  }, [value, isStreaming, isConnected, onSend])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  const canSend = value.trim().length > 0 && !isStreaming && isConnected

  const inputRow = (
    <>
      <button
        type="button"
        tabIndex={-1}
        className="flex-shrink-0 p-1 text-white/40 hover:text-white/70 transition-colors"
      >
        <Plus size={18} />
      </button>

      <textarea
        ref={textareaRef}
        data-chat-input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          isStreaming
            ? 'Yuno is responding…'
            : !isConnected
            ? 'Connecting…'
            : 'Ask anything'
        }
        disabled={isStreaming || !isConnected}
        rows={1}
        className="flex-1 bg-transparent text-white text-sm leading-6 resize-none outline-none placeholder-[#686868] disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ minHeight: `${BASE_HEIGHT}px` }}
      />

      <div className="flex items-center gap-1.5 flex-shrink-0">
        {!canSend && !isStreaming && (
          <button
            type="button"
            tabIndex={-1}
            className="p-1.5 text-white/40 hover:text-white/70 transition-colors"
          >
            <Mic size={16} />
          </button>
        )}
        <button
          onClick={isStreaming ? onStop : handleSend}
          type="button"
          disabled={!canSend && !isStreaming}
          title={canSend ? 'Send (Enter)' : isStreaming ? 'Stop generation' : 'Type a message'}
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-150',
            canSend
              ? 'bg-white text-black hover:bg-white/90 active:scale-95'
              : isStreaming
              ? 'bg-white/20 text-white cursor-pointer hover:bg-white/30 active:scale-95'
              : 'bg-[#2a2a2a] text-white/20 cursor-not-allowed'
          )}
        >
          {isStreaming ? (
            <Square size={10} className="fill-current" />
          ) : (
            <ArrowUp size={15} />
          )}
        </button>
      </div>
    </>
  )

  if (variant === 'pill') {
    return (
      <div
        className={cn(
          'flex items-end gap-2 px-4 py-3.5 rounded-3xl',
          'bg-[#1f1f1f] border border-white/[0.08]',
          'focus-within:border-white/[0.16] transition-all duration-200'
        )}
      >
        {inputRow}
      </div>
    )
  }

  return (
    <div className="flex-shrink-0 bg-[#0d0d0d] px-4 pb-5 pt-2">
      <div className="max-w-3xl mx-auto space-y-2">
        <div
          className={cn(
            'flex items-end gap-2 px-4 py-3.5 rounded-3xl',
            'bg-[#1f1f1f] border transition-all duration-200',
            isStreaming
              ? 'border-white/[0.06]'
              : 'border-white/[0.08] hover:border-white/[0.12] focus-within:border-white/[0.2]'
          )}
        >
          {inputRow}
        </div>
        <p className="text-white/20 text-[11px] text-center">
          Yuno can make mistakes. Verify important information.
        </p>
      </div>
    </div>
  )
}
