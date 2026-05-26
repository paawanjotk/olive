'use client'

import { useState } from 'react'
import { Calculator, ChevronDown, ChevronRight, Clock, Globe, CheckCircle2 } from 'lucide-react'
import type { ToolCall } from '@/lib/types'

// ── Tool display config ────────────────────────────────────────────────────

const TOOL_CONFIG: Record<string, { icon: React.ReactNode; label: string }> = {
  web_search:   { icon: <Globe size={14} />,       label: 'Searched the web' },
  calculator:   { icon: <Calculator size={14} />,  label: 'Calculated' },
  get_datetime: { icon: <Clock size={14} />,       label: 'Got date/time' },
}

function getConfig(name: string) {
  return TOOL_CONFIG[name] ?? { icon: <Globe size={14} />, label: name.replace(/_/g, ' ') }
}

// ── Parse web search results from Tavily formatted string ─────────────────

interface SearchResult {
  title: string
  url: string
  snippet: string
}

function parseWebResults(raw: string): SearchResult[] {
  const results: SearchResult[] = []
  const blocks = raw.split('\n\n').filter(Boolean)
  for (const block of blocks) {
    const lines = block.split('\n')
    const titleLine = lines.find((l) => l.startsWith('**'))
    const sourceLine = lines.find((l) => l.startsWith('Source:'))
    if (titleLine && sourceLine) {
      const title = titleLine.replace(/\*\*/g, '').trim()
      const url = sourceLine.replace('Source:', '').trim()
      const snippet = lines.filter((l) => !l.startsWith('**') && !l.startsWith('Source:')).join(' ').trim()
      results.push({ title, url, snippet: snippet.slice(0, 100) })
    }
  }
  return results
}

function getDomain(url: string): string {
  try { return new URL(url).hostname.replace('www.', '') }
  catch { return url }
}

// ── Input summary (collapsed label) ───────────────────────────────────────

function inputSummary(tool_name: string, input: Record<string, unknown>): string {
  if (tool_name === 'web_search' && input.query) return String(input.query)
  if (tool_name === 'calculator' && input.expression) return String(input.expression)
  if (tool_name === 'get_datetime') return String(input.timezone ?? 'UTC')
  const first = Object.values(input)[0]
  return first ? String(first).slice(0, 50) : ''
}

// ── Expanded content per tool type ────────────────────────────────────────

function WebSearchExpanded({ call }: { call: ToolCall }) {
  const query = String(call.tool_input.query ?? '')
  const results = call.tool_result ? parseWebResults(call.tool_result) : []

  return (
    <div className="mt-2 rounded-xl border border-white/[0.08] overflow-hidden bg-[#181818]">
      {/* Query header */}
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/[0.06]">
        <Globe size={14} className="text-white/40 shrink-0" />
        <span className="text-[13px] text-white/80 flex-1">{query}</span>
        {results.length > 0 && (
          <span className="text-[11px] text-white/30">{results.length} results</span>
        )}
      </div>

      {/* Results */}
      {results.slice(0, 5).map((r, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-2.5 border-b border-white/[0.04] last:border-0">
          <div className="w-4 h-4 rounded-sm bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
            <Globe size={9} className="text-white/40" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[12px] text-white/70 truncate">{r.title}</div>
            <div className="text-[11px] text-white/30 truncate">{getDomain(r.url)}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function CalculatorExpanded({ call }: { call: ToolCall }) {
  return (
    <div className="mt-2 rounded-xl border border-white/[0.08] overflow-hidden bg-[#181818] px-4 py-3">
      <div className="text-[12px] font-mono text-white/60">{String(call.tool_input.expression ?? '')}</div>
      {call.tool_result && (
        <div className="text-[18px] font-mono text-white/90 mt-1">= {call.tool_result}</div>
      )}
    </div>
  )
}

function DatetimeExpanded({ call }: { call: ToolCall }) {
  return (
    <div className="mt-2 rounded-xl border border-white/[0.08] bg-[#181818] px-4 py-3">
      <div className="text-[13px] text-white/70 font-mono">{call.tool_result}</div>
    </div>
  )
}

function ExpandedContent({ call }: { call: ToolCall }) {
  if (call.tool_name === 'web_search') return <WebSearchExpanded call={call} />
  if (call.tool_name === 'calculator') return <CalculatorExpanded call={call} />
  if (call.tool_name === 'get_datetime') return <DatetimeExpanded call={call} />
  return (
    <div className="mt-2 rounded-xl border border-white/[0.08] bg-[#181818] px-4 py-3">
      <pre className="text-[11px] font-mono text-white/50 whitespace-pre-wrap">
        {call.tool_result?.slice(0, 300)}
      </pre>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export default function ToolCallBubble({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false)
  const { icon, label } = getConfig(call.tool_name)
  const summary = inputSummary(call.tool_name, call.tool_input)
  const isDone = call.status === 'done'

  return (
    <div className="flex items-start gap-3 py-1.5 animate-[fade-in_0.15s_ease-out]">
      {/* Spacer to align with assistant messages */}
      <div className="w-7 h-7 flex-shrink-0" />

      <div className="flex-1 min-w-0 max-w-2xl">
        {/* Toggle row */}
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 text-[13px] text-white/40 hover:text-white/60 transition-colors py-0.5 group"
        >
          <span className={`transition-colors ${isDone ? 'text-white/40' : 'text-blue-400/70'}`}>{icon}</span>
          <span>{label}</span>
          {summary && !expanded && (
            <span className="text-white/25 max-w-[200px] truncate">{summary}</span>
          )}
          {isDone ? (
            expanded
              ? <ChevronDown size={13} className="text-white/30" />
              : <ChevronRight size={13} className="text-white/30" />
          ) : (
            <span className="w-3 h-3 rounded-full border border-blue-400/40 border-t-blue-400 animate-spin ml-1" />
          )}
        </button>

        {/* Expanded details */}
        {expanded && isDone && <ExpandedContent call={call} />}

        {/* Done indicator */}
        {expanded && isDone && (
          <div className="flex items-center gap-1.5 mt-3 text-[12px] text-white/30">
            <CheckCircle2 size={13} className="text-white/25" />
            <span>Done</span>
          </div>
        )}
      </div>
    </div>
  )
}
