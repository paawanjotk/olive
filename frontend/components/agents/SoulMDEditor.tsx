'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'

const SOUL_PLACEHOLDER = `# Agent Soul

## Philosophy
Describe the agent's core beliefs and reasoning approach.

## Personality
Key character traits that shape how it communicates.

## Communication Style
- How it structures responses
- Tone and formality level
- Any specific patterns it follows

## Operational Behavior
- What it prioritizes
- How it handles uncertainty
- Any constraints it self-imposes`

interface SoulMDEditorProps {
  value: string
  onChange: (v: string) => void
}

export default function SoulMDEditor({ value, onChange }: SoulMDEditorProps) {
  const [tab, setTab] = useState<'write' | 'preview'>('write')

  const renderPreview = () => {
    if (!value.trim()) {
      return <p className="text-white/20 text-sm italic">Nothing to preview yet.</p>
    }
    // Simple markdown rendering — headings, bold, bullets, paragraphs
    const lines = value.split('\n')
    return (
      <div className="space-y-1 text-sm text-white/70 leading-relaxed">
        {lines.map((line, i) => {
          if (line.startsWith('## ')) return <h3 key={i} className="text-white font-semibold mt-3 first:mt-0 text-base">{line.slice(3)}</h3>
          if (line.startsWith('# '))  return <h2 key={i} className="text-white font-bold mt-4 first:mt-0 text-lg">{line.slice(2)}</h2>
          if (line.startsWith('- '))  return <li key={i} className="ml-4 list-disc">{line.slice(2)}</li>
          if (line.trim() === '')     return <div key={i} className="h-1" />
          return <p key={i}>{line}</p>
        })}
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-white/[0.08] overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-white/[0.06] bg-white/[0.02]">
        {(['write', 'preview'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              'px-4 py-2 text-xs font-medium capitalize transition-colors',
              tab === t
                ? 'text-white border-b border-white/40 -mb-px'
                : 'text-white/30 hover:text-white/60'
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'write' ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={SOUL_PLACEHOLDER}
          rows={12}
          className="w-full bg-transparent text-white/80 text-sm p-4 resize-none outline-none placeholder-white/20 font-mono leading-relaxed"
        />
      ) : (
        <div className="p-4 min-h-[200px]">
          {renderPreview()}
        </div>
      )}
    </div>
  )
}
