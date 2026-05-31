'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  ArrowLeft, Loader2, CheckCircle2, XCircle, Pause, Square, RotateCcw,
  Wrench, GitBranch, Cpu, Shield, Zap, AlertTriangle,
} from 'lucide-react'
import {
  getExecutionTrace, approveCheckpoint,
  pauseExecution, resumeExecution, terminateExecution,
} from '@/lib/api'
import type { ExecutionTrace, TraceSpan, SpanEvent, ExecutionWithWorkflow } from '@/lib/types'
import { useExecutionStream } from '@/hooks/useExecutionStream'
import { cn } from '@/lib/utils'

// ── Helpers ───────────────────────────────────────────────────────────────────

function ms(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n < 1000) return `${n}ms`
  if (n < 60_000) return `${(n / 1000).toFixed(2)}s`
  return `${Math.floor(n / 60_000)}m ${((n % 60_000) / 1000).toFixed(0)}s`
}

function tok(n: number | null | undefined): string {
  if (!n) return '—'
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

function usd(n: number | null | undefined): string {
  if (!n) return '—'
  return n < 0.001 ? `$${n.toFixed(6)}` : `$${n.toFixed(4)}`
}

function throughput(outTok: number | null | undefined, durationMs: number | null | undefined): string {
  if (!outTok || !durationMs || durationMs === 0) return '—'
  return `${(outTok / (durationMs / 1000)).toFixed(1)} t/s`
}

function ts(d: string | null | undefined): string {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-US', {
    year: 'numeric', month: 'numeric', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })
}

function prettyJson(v: unknown): string {
  if (v == null) return ''
  if (typeof v === 'string') return v
  try { return JSON.stringify(v, null, 2) } catch { return String(v) }
}

// ── Type configs ──────────────────────────────────────────────────────────────

type SpanMeta = { label: string; icon: React.ElementType; dot: string; badge: string }

const SPAN_META: Record<string, SpanMeta> = {
  agent:      { label: 'AGENT',      icon: Cpu,       dot: 'bg-blue-400',   badge: 'text-blue-400 bg-blue-400/15' },
  supervisor: { label: 'SUPERVISOR', icon: GitBranch, dot: 'bg-violet-400', badge: 'text-violet-400 bg-violet-400/15' },
  checkpoint: { label: 'CHECKPOINT', icon: Shield,    dot: 'bg-amber-400',  badge: 'text-amber-400 bg-amber-400/15' },
  trigger:    { label: 'TRIGGER',    icon: Zap,       dot: 'bg-teal-400',   badge: 'text-teal-400 bg-teal-400/15' },
  end:        { label: 'END',        icon: Square,    dot: 'bg-white/20',   badge: 'text-white/30 bg-white/[0.06]' },
}

function spanMeta(type: string): SpanMeta {
  return SPAN_META[type] ?? { label: type.toUpperCase(), icon: Cpu, dot: 'bg-white/30', badge: 'text-white/40 bg-white/[0.06]' }
}

function statusDot(status: string, live = false): string {
  const m: Record<string, string> = {
    completed: 'bg-emerald-400',
    failed:    'bg-red-400',
    running:   'bg-blue-400',
    pending:   'bg-yellow-400/80',
    paused:    'bg-orange-400',
    cancelled: 'bg-white/20',
  }
  return cn('w-1.5 h-1.5 rounded-full shrink-0', m[status] ?? 'bg-white/20', (live || status === 'running') && 'animate-pulse')
}

// ── Badge ─────────────────────────────────────────────────────────────────────

function Badge({ label, cls }: { label: string; cls: string }) {
  return (
    <span className={cn('px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-wider', cls)}>
      {label}
    </span>
  )
}

// ── Selection state ───────────────────────────────────────────────────────────

type Selected =
  | { kind: 'root' }
  | { kind: 'span'; span: TraceSpan }
  | { kind: 'event'; event: SpanEvent; span: TraceSpan }

// ── Right panel: KV row ───────────────────────────────────────────────────────

function KV({ k, v, vCls }: { k: string; v: React.ReactNode; vCls?: string }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-white/[0.04] last:border-0">
      <span className="text-[10px] text-white/35 uppercase tracking-[0.06em]">{k}</span>
      <span className={cn('text-xs font-mono text-right', vCls ?? 'text-white/70')}>{v}</span>
    </div>
  )
}

// ── Section header ─────────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <p className="text-[10px] font-semibold text-white/30 uppercase tracking-[0.09em] mb-2">{title}</p>
  )
}

// ── Code block ────────────────────────────────────────────────────────────────

function CodeBlock({ value, maxH = 'max-h-52' }: { value: string; maxH?: string }) {
  if (!value.trim()) return null
  return (
    <pre className={cn('text-[11px] font-mono leading-relaxed text-white/65 bg-[#0d0d0d] border border-white/[0.06] rounded-xl p-4 overflow-auto whitespace-pre-wrap break-words', maxH)}>
      {value}
    </pre>
  )
}

// ── Root detail ────────────────────────────────────────────────────────────────

function RootDetail({ trace, liveTokens, liveCost }: {
  trace: ExecutionTrace
  liveTokens: number
  liveCost: number
}) {
  const totalTok = liveTokens || (trace.total_input_tokens + trace.total_output_tokens)
  const totalCost = liveCost || trace.total_cost_usd
  const input = trace.input_text

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-white font-semibold text-base">{trace.workflow_name}</p>
          <p className="text-white/30 text-[11px] font-mono mt-0.5">{trace.execution_id}</p>
        </div>
        <p className="text-white/30 text-[11px] font-mono shrink-0">{ts(trace.started_at)}</p>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-px bg-white/[0.06] rounded-xl overflow-hidden border border-white/[0.06]">
        {/* Timing */}
        <div className="bg-[#111] p-4 space-y-2.5">
          <SectionHeader title="Timing" />
          <KV k="Total" v={ms(trace.duration_ms)} />
          <KV k="Throughput" v={throughput(trace.total_output_tokens, trace.duration_ms)} />
          <KV k="Spans" v={trace.spans.length} />
        </div>
        {/* Usage */}
        <div className="bg-[#111] p-4 space-y-2.5">
          <SectionHeader title="Usage" />
          <KV k="Input" v={tok(trace.total_input_tokens)} />
          <KV k="Output" v={tok(trace.total_output_tokens)} />
          <KV k="Total" v={tok(totalTok)} />
          <KV k="Cost" v={usd(totalCost)} vCls="text-emerald-400" />
        </div>
        {/* Workflow */}
        <div className="bg-[#111] p-4 space-y-2.5">
          <SectionHeader title="Run" />
          <KV k="Trigger" v={trace.trigger_type} />
          <KV k="Status" v={trace.status} vCls={trace.status === 'completed' ? 'text-emerald-400' : trace.status === 'failed' ? 'text-red-400' : 'text-white/70'} />
          <KV k="Started" v={ts(trace.started_at)} />
          <KV k="Ended" v={ts(trace.completed_at)} />
        </div>
      </div>

      {input && (
        <div>
          <SectionHeader title="Input" />
          <CodeBlock value={input} />
        </div>
      )}

      {trace.output_text && (
        <div>
          <SectionHeader title="Output" />
          <CodeBlock value={trace.output_text} maxH="max-h-96" />
        </div>
      )}

      {trace.error_message && (
        <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4 flex gap-2">
          <AlertTriangle size={13} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-400 text-xs font-mono leading-relaxed">{trace.error_message}</p>
        </div>
      )}
    </div>
  )
}

// ── Span detail ────────────────────────────────────────────────────────────────

function SpanDetail({ span, liveOutput, liveStatus }: {
  span: TraceSpan
  liveOutput?: string
  liveStatus?: string
}) {
  const meta = spanMeta(span.span_type)
  const Icon = meta.icon
  const status = liveStatus || span.status
  const outText = liveOutput || span.output?.text || ''
  const decision = span.output?.decision as { next?: string; reason?: string } | undefined
  const totalTok = (span.input_tokens ?? 0) + (span.output_tokens ?? 0)

  const inputText = prettyJson(span.input?.prompt ?? span.input)
  const outputDisplay = decision
    ? prettyJson(decision)
    : outText

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className={cn('p-2 rounded-lg shrink-0', meta.badge.split(' ')[1])}>
            <Icon size={14} className={meta.badge.split(' ')[0]} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <p className="text-white font-semibold text-sm">{span.node_label}</p>
              <Badge label={meta.label} cls={meta.badge} />
              <span className={statusDot(status, status === 'running')} />
            </div>
            {span.agent_name && (
              <p className="text-white/35 text-[11px] mt-0.5">{span.agent_name}</p>
            )}
          </div>
        </div>
        <p className="text-white/30 text-[11px] font-mono shrink-0">{ts(span.started_at)}</p>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-px bg-white/[0.06] rounded-xl overflow-hidden border border-white/[0.06]">
        <div className="bg-[#111] p-4 space-y-2.5">
          <SectionHeader title="Timing" />
          <KV k="Total" v={ms(span.duration_ms)} />
          <KV k="First token" v="—" />
          <KV k="Throughput" v={throughput(span.output_tokens, span.duration_ms)} />
        </div>
        <div className="bg-[#111] p-4 space-y-2.5">
          <SectionHeader title="Usage" />
          <KV k="Prompt" v={tok(span.input_tokens)} />
          <KV k="Completion" v={tok(span.output_tokens)} />
          <KV k="Total" v={tok(totalTok || null)} />
          <KV k="Cost" v={usd(span.cost_usd)} vCls="text-emerald-400" />
        </div>
        <div className="bg-[#111] p-4 space-y-2.5">
          <SectionHeader title="Model" />
          <KV k="Provider" v={span.provider ? span.provider.charAt(0).toUpperCase() + span.provider.slice(1) : '—'} />
          <KV k="Model" v={span.model ?? '—'} />
          <KV k="Max tokens" v={span.max_tokens ? String(span.max_tokens) : '—'} />
        </div>
      </div>

      {/* Supervisor decision callout */}
      {decision && (
        <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 space-y-1.5">
          <p className="text-[10px] font-bold text-violet-400/60 uppercase tracking-wide">Routing Decision</p>
          <p className="text-white text-sm font-mono">→ {decision.next}</p>
          {decision.reason && <p className="text-white/45 text-xs leading-relaxed">{decision.reason}</p>}
        </div>
      )}

      {/* Live streaming */}
      {status === 'running' && liveOutput && (
        <div>
          <SectionHeader title="Live Output" />
          <div className="rounded-xl border border-blue-500/20 bg-[#0d1117] p-4">
            <div className="flex items-center gap-1.5 mb-2">
              <Loader2 size={10} className="animate-spin text-blue-400" />
              <span className="text-[10px] text-blue-400/60 font-mono uppercase tracking-wide">streaming</span>
            </div>
            <pre className="text-white/70 text-[11px] font-mono leading-relaxed whitespace-pre-wrap max-h-40 overflow-auto">
              {liveOutput}
            </pre>
          </div>
        </div>
      )}

      {/* Input */}
      {inputText && (
        <div>
          <SectionHeader title="Input" />
          <CodeBlock value={inputText} />
        </div>
      )}

      {/* Output */}
      {outputDisplay && !liveOutput && (
        <div>
          <SectionHeader title="Output" />
          <CodeBlock value={outputDisplay} maxH="max-h-80" />
        </div>
      )}

      {/* Error */}
      {span.error_message && (
        <div className="rounded-xl border border-red-500/25 bg-red-500/5 p-4 flex gap-2">
          <AlertTriangle size={13} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-400 text-xs font-mono leading-relaxed">{span.error_message}</p>
        </div>
      )}

      {/* Context */}
      <div>
        <SectionHeader title="Context" />
        <div className="rounded-xl border border-white/[0.06] bg-[#0d0d0d] px-4 py-2">
          <KV k="Node ID" v={span.node_id} />
          <KV k="Span ID" v={span.id.slice(0, 24) + '…'} />
          <KV k="Status" v={status} />
          <KV k="Started" v={ts(span.started_at)} />
          <KV k="Completed" v={ts(span.completed_at)} />
        </div>
      </div>
    </div>
  )
}

// ── Tool event detail ─────────────────────────────────────────────────────────

function EventDetail({ event, span }: { event: SpanEvent; span: TraceSpan }) {
  const isStart = event.event_type === 'tool_start'
  const toolName = event.payload.tool_name as string | undefined
  const toolInput = event.payload.tool_input
  const toolResult = event.payload.tool_result as string | undefined

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-400/10 shrink-0">
            <Wrench size={14} className="text-amber-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <p className="text-white font-semibold text-sm">{toolName ?? 'Tool call'}</p>
              <Badge label="TOOL" cls="text-amber-400 bg-amber-400/15" />
              <Badge
                label={isStart ? 'START' : 'END'}
                cls={isStart ? 'text-blue-400 bg-blue-400/10' : 'text-emerald-400 bg-emerald-400/10'}
              />
            </div>
            <p className="text-white/35 text-[11px] mt-0.5">in {span.node_label}</p>
          </div>
        </div>
        <p className="text-white/30 text-[11px] font-mono shrink-0">{ts(event.created_at)}</p>
      </div>

      {toolInput != null && (
        <div>
          <SectionHeader title="Input" />
          <CodeBlock value={prettyJson(toolInput)} />
        </div>
      )}

      {toolResult != null && (
        <div>
          <SectionHeader title="Result" />
          <CodeBlock value={prettyJson(toolResult)} maxH="max-h-80" />
        </div>
      )}

      <div>
        <SectionHeader title="Context" />
        <div className="rounded-xl border border-white/[0.06] bg-[#0d0d0d] px-4 py-2">
          <KV k="Tool" v={toolName ?? '—'} />
          <KV k="Event" v={event.event_type} />
          <KV k="Parent span" v={span.node_label} />
          <KV k="Timestamp" v={ts(event.created_at)} />
        </div>
      </div>
    </div>
  )
}

// ── Span tree ─────────────────────────────────────────────────────────────────

function SpanTree({
  trace,
  selected,
  onSelect,
  nodeStatus,
  nodeOutputs,
}: {
  trace: ExecutionTrace
  selected: Selected
  onSelect: (s: Selected) => void
  nodeStatus: Record<string, string>
  nodeOutputs: Record<string, string>
}) {
  // Pair tool_start + tool_end events into tool call rows
  function toolRows(events: SpanEvent[]): { start: SpanEvent; end?: SpanEvent }[] {
    const rows: { start: SpanEvent; end?: SpanEvent }[] = []
    const seen = new Set<string>()
    for (const ev of events) {
      if (ev.event_type !== 'tool_start') continue
      const name = ev.payload.tool_name as string
      const end = events.find(
        (e) => e.event_type === 'tool_end' && e.payload.tool_name === name && !seen.has(e.id)
      )
      if (end) seen.add(end.id)
      rows.push({ start: ev, end })
    }
    return rows
  }

  return (
    <div className="flex-1 overflow-y-auto py-2">
      {/* Root row */}
      <button
        onClick={() => onSelect({ kind: 'root' })}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2.5 text-left transition-colors',
          selected.kind === 'root' ? 'bg-white/[0.08]' : 'hover:bg-white/[0.04]',
        )}
      >
        <span className={statusDot(trace.status, trace.status === 'running')} />
        <span className="flex-1 text-[11px] font-semibold text-white/80 truncate">{trace.workflow_name}</span>
        <Badge label="ROOT" cls="text-white/40 bg-white/[0.06]" />
      </button>

      {/* Span rows */}
      {trace.spans.map((span) => {
        const liveNs = nodeStatus[span.node_id] as string | undefined
        const liveStatus = liveNs === 'running' ? 'running' : liveNs === 'completed' ? 'completed' : liveNs === 'failed' ? 'failed' : undefined
        const effStatus = liveStatus ?? span.status
        const meta = spanMeta(span.span_type)
        const isSpanSelected = selected.kind === 'span' && selected.span.id === span.id
        const tools = toolRows(span.events)

        return (
          <div key={span.id}>
            {/* Span row */}
            <button
              onClick={() => onSelect({ kind: 'span', span })}
              className={cn(
                'w-full flex items-center gap-2 px-3 py-2.5 pl-6 text-left transition-colors',
                isSpanSelected ? 'bg-white/[0.08]' : 'hover:bg-white/[0.04]',
              )}
            >
              <span className={statusDot(effStatus, liveNs === 'running')} />
              <span className={cn('flex-1 min-w-0 text-[11px] truncate', isSpanSelected ? 'text-white font-medium' : 'text-white/70')}>
                {span.node_label}
              </span>
              <Badge label={meta.label} cls={meta.badge} />
              {span.duration_ms != null && (
                <span className="text-[10px] font-mono text-white/25 ml-1">{ms(span.duration_ms)}</span>
              )}
            </button>

            {/* Tool call sub-rows */}
            {tools.map(({ start, end }) => {
              const toolName = (start.payload.tool_name as string) || 'tool'
              const isEvSelected = selected.kind === 'event' && selected.event.id === start.id
              return (
                <button
                  key={start.id}
                  onClick={() => onSelect({ kind: 'event', event: start, span })}
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-2 pl-10 text-left transition-colors',
                    isEvSelected ? 'bg-white/[0.06]' : 'hover:bg-white/[0.03]',
                  )}
                >
                  <Wrench size={9} className="text-amber-400/70 shrink-0" />
                  <span className={cn('flex-1 min-w-0 text-[10px] font-mono truncate', isEvSelected ? 'text-amber-300' : 'text-amber-400/70')}>
                    {toolName}
                  </span>
                  <Badge label="TOOL" cls="text-amber-400/80 bg-amber-400/10" />
                  {end && start.created_at && end.created_at && (
                    <span className="text-[9px] font-mono text-white/20 ml-1">
                      {ms(new Date(end.created_at).getTime() - new Date(start.created_at).getTime())}
                    </span>
                  )}
                </button>
              )
            })}

            {/* Live running node not yet completed */}
            {liveNs === 'running' && nodeOutputs[span.node_id] && !span.output?.text && (
              <div className="pl-10 pr-3 py-1.5">
                <p className="text-[10px] text-blue-400/50 font-mono truncate">
                  {nodeOutputs[span.node_id].slice(-80)}…
                </p>
              </div>
            )}
          </div>
        )
      })}

      {/* Live spans not yet flushed to DB */}
      {Object.entries(nodeStatus)
        .filter(([nid, ns]) => ns === 'running' && !trace.spans.some((s) => s.node_id === nid))
        .map(([nid]) => (
          <div key={nid} className="flex items-center gap-2 px-3 py-2.5 pl-6 opacity-60">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
            <span className="flex-1 text-[11px] text-blue-400/70 font-mono truncate">{nid}</span>
            <Badge label="RUNNING" cls="text-blue-400/70 bg-blue-400/10" />
          </div>
        ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function TraceView({
  execution,
  onBack,
  onRefresh,
}: {
  execution: ExecutionWithWorkflow
  onBack: () => void
  onRefresh: () => void
}) {
  const [trace, setTrace] = useState<ExecutionTrace | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Selected>({ kind: 'root' })
  const [controlling, setControlling] = useState(false)
  const [approving, setApproving] = useState(false)

  const isLive = execution.status === 'running' || execution.status === 'pending'
  const isPaused = execution.status === 'paused'

  const stream = useExecutionStream(isLive || isPaused ? execution.id : null)
  const { nodeStatus, nodeOutputs, totalTokens, totalCost, pendingApproval } = stream

  const loadTrace = useCallback(() => {
    setLoading(true)
    getExecutionTrace(execution.id)
      .then((t) => setTrace(t))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [execution.id])

  useEffect(() => { loadTrace() }, [loadTrace])

  useEffect(() => {
    if (!isLive) {
      const tid = setTimeout(loadTrace, 1000)
      return () => clearTimeout(tid)
    }
  }, [stream.status, isLive, loadTrace])

  const handleControl = async (action: 'pause' | 'resume' | 'terminate') => {
    setControlling(true)
    try {
      if (action === 'pause') await pauseExecution(execution.id)
      else if (action === 'resume') await resumeExecution(execution.id)
      else await terminateExecution(execution.id)
      onRefresh()
    } finally { setControlling(false) }
  }

  const handleApprove = async (approved: boolean) => {
    if (!pendingApproval) return
    setApproving(true)
    try { await approveCheckpoint(execution.id, pendingApproval.nodeId, approved) }
    finally { setApproving(false) }
  }

  // Derive right-panel content
  const getSpanForSelected = (): TraceSpan | null => {
    if (!trace) return null
    if (selected.kind === 'span') return selected.span
    if (selected.kind === 'event') return selected.span
    return null
  }
  const selSpan = getSpanForSelected()

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a]">

      {/* ── Header ── */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-white/[0.06] shrink-0">
        <button onClick={onBack} className="p-1.5 rounded-lg text-white/35 hover:text-white hover:bg-white/[0.06] transition-colors shrink-0">
          <ArrowLeft size={14} />
        </button>

        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-white text-sm font-semibold truncate">{execution.workflow_name}</span>
          <span className={statusDot(execution.status, isLive)} />
          <span className="text-[10px] font-mono text-white/30 border border-white/[0.06] px-1.5 py-0.5 rounded shrink-0">{execution.trigger_type}</span>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs shrink-0">
          {(trace?.total_input_tokens || trace?.total_output_tokens) && (
            <span className="text-white/35">{tok((trace.total_input_tokens + trace.total_output_tokens) || null)} tok</span>
          )}
          {(isLive ? totalCost : trace?.total_cost_usd ?? 0) > 0 && (
            <span className="text-emerald-400/70">{usd(isLive ? totalCost : trace?.total_cost_usd)}</span>
          )}
          {trace?.duration_ms != null && (
            <span className="text-white/30">{ms(trace.duration_ms)}</span>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {isLive && (
            <button onClick={() => handleControl('pause')} disabled={controlling}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 text-[11px] font-medium disabled:opacity-40 transition-colors">
              <Pause size={10} /> Pause
            </button>
          )}
          {isPaused && (
            <button onClick={() => handleControl('resume')} disabled={controlling}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-[11px] font-medium disabled:opacity-40 transition-colors">
              <RotateCcw size={10} /> Resume
            </button>
          )}
          {execution.status === 'failed' && (
            <button onClick={() => handleControl('resume')} disabled={controlling}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 text-[11px] font-medium disabled:opacity-40 transition-colors">
              <RotateCcw size={10} /> Retry
            </button>
          )}
          {(isLive || isPaused) && (
            <button onClick={() => handleControl('terminate')} disabled={controlling}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 text-[11px] font-medium disabled:opacity-40 transition-colors">
              <Square size={10} /> Stop
            </button>
          )}
        </div>
      </div>

      {/* ── Approval banner ── */}
      {pendingApproval && (
        <div className="mx-4 mt-3 rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 shrink-0">
          <div className="flex items-center gap-2 mb-2">
            <Pause size={12} className="text-amber-400" />
            <span className="text-amber-400 text-xs font-semibold">Human approval required</span>
          </div>
          {pendingApproval.preview && (
            <pre className="text-white/50 text-[11px] bg-black/20 rounded-lg p-3 mb-3 overflow-auto max-h-24 whitespace-pre-wrap font-mono">
              {pendingApproval.preview}
            </pre>
          )}
          <div className="flex gap-2">
            <button onClick={() => handleApprove(true)} disabled={approving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 text-xs font-medium disabled:opacity-50">
              <CheckCircle2 size={12} /> Approve
            </button>
            <button onClick={() => handleApprove(false)} disabled={approving}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/15 text-red-400 hover:bg-red-500/25 text-xs font-medium disabled:opacity-50">
              <XCircle size={12} /> Reject
            </button>
          </div>
        </div>
      )}

      {/* ── Body ── */}
      {loading && !trace ? (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 size={16} className="animate-spin text-white/20" />
        </div>
      ) : trace ? (
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* Left: span tree */}
          <div className="w-56 shrink-0 border-r border-white/[0.06] flex flex-col overflow-hidden">
            <SpanTree
              trace={trace}
              selected={selected}
              onSelect={setSelected}
              nodeStatus={nodeStatus}
              nodeOutputs={nodeOutputs}
            />
            {/* Footer */}
            <div className="px-3 py-2 border-t border-white/[0.04]">
              <p className="text-[9px] font-mono text-white/20">
                {trace.spans.length} span{trace.spans.length !== 1 ? 's' : ''} · {trace.spans.reduce((a, s) => a + s.events.filter(e => e.event_type === 'tool_start').length, 0)} tool calls
              </p>
            </div>
          </div>

          {/* Right: detail */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {selected.kind === 'root' && (
              <RootDetail trace={trace} liveTokens={totalTokens} liveCost={totalCost} />
            )}
            {selected.kind === 'span' && selSpan && (
              <SpanDetail
                span={selSpan}
                liveOutput={nodeOutputs[selSpan.node_id]}
                liveStatus={
                  nodeStatus[selSpan.node_id] === 'running' ? 'running'
                  : nodeStatus[selSpan.node_id] === 'completed' ? 'completed'
                  : nodeStatus[selSpan.node_id] === 'failed' ? 'failed'
                  : undefined
                }
              />
            )}
            {selected.kind === 'event' && (
              <EventDetail event={selected.event} span={selected.span} />
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-white/20 text-sm">
          Trace not available
        </div>
      )}
    </div>
  )
}
