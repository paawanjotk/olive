'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  Activity, RefreshCw, Loader2, AlertCircle, CheckCircle2,
  XCircle, Pause, Square, ChevronRight, Play,
  Clock, Zap, MessageSquare,
} from 'lucide-react'
import { listAllExecutions } from '@/lib/api'
import type { ExecutionWithWorkflow } from '@/lib/types'
import { cn } from '@/lib/utils'
import TraceView from './TraceView'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtMs(start: string | null, end: string | null): string {
  if (!start) return '—'
  const ms = (end ? new Date(end) : new Date()).getTime() - new Date(start).getTime()
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`
}

function fmtTime(ts: string | null): string {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

// ── Status indicator ──────────────────────────────────────────────────────────

const STATUS: Record<string, { color: string; dot: string; icon: React.ElementType; label: string }> = {
  running:   { color: 'text-blue-400',    dot: 'bg-blue-400 animate-pulse',   icon: Loader2,      label: 'Running' },
  completed: { color: 'text-emerald-400', dot: 'bg-emerald-400',              icon: CheckCircle2, label: 'Completed' },
  failed:    { color: 'text-red-400',     dot: 'bg-red-400',                  icon: XCircle,      label: 'Failed' },
  pending:   { color: 'text-yellow-400',  dot: 'bg-yellow-400',               icon: Clock,        label: 'Pending' },
  paused:    { color: 'text-orange-400',  dot: 'bg-orange-400',               icon: Pause,        label: 'Paused' },
  cancelled: { color: 'text-white/30',    dot: 'bg-white/20',                 icon: Square,       label: 'Cancelled' },
}

function StatusPill({ status }: { status: string }) {
  const s = STATUS[status] ?? STATUS.pending
  const Icon = s.icon
  return (
    <span className={cn('inline-flex items-center gap-1 text-[10px] font-medium', s.color)}>
      <Icon size={10} className={status === 'running' ? 'animate-spin' : ''} />
      {s.label}
    </span>
  )
}

const TRIGGER_STYLE: Record<string, string> = {
  manual:   'text-white/35 bg-white/[0.05] border-white/[0.06]',
  slack:    'text-purple-400 bg-purple-400/10 border-purple-400/20',
  telegram: 'text-sky-400 bg-sky-400/10 border-sky-400/20',
  chat:     'text-orange-400 bg-orange-400/10 border-orange-400/20',
  schedule: 'text-teal-400 bg-teal-400/10 border-teal-400/20',
}

function TriggerPill({ trigger }: { trigger: string }) {
  const icons: Record<string, React.ElementType> = {
    manual: Zap, slack: MessageSquare, telegram: MessageSquare,
    chat: MessageSquare, schedule: Clock,
  }
  const Icon = icons[trigger] ?? Zap
  return (
    <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] font-mono uppercase tracking-wide', TRIGGER_STYLE[trigger] ?? TRIGGER_STYLE.manual)}>
      <Icon size={9} />
      {trigger}
    </span>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, color, icon: Icon }: {
  label: string; value: string | number; color: string; icon: React.ElementType
}) {
  return (
    <div className="rounded-2xl border border-white/[0.06] bg-[#111] p-4">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon size={11} className={color} />
        <span className="text-[10px] text-white/35 uppercase tracking-wide">{label}</span>
      </div>
      <p className={cn('text-2xl font-mono font-light tracking-tight', color)}>{value}</p>
    </div>
  )
}

// ── Execution row ─────────────────────────────────────────────────────────────

function ExRow({ ex, onClick }: { ex: ExecutionWithWorkflow; onClick: () => void }) {
  const s = STATUS[ex.status] ?? STATUS.pending
  const inputText = (ex.input_data?.input as string | undefined) ?? ''
  const isActive = ex.status === 'running' || ex.status === 'pending'

  return (
    <button
      onClick={onClick}
      className="w-full group text-left rounded-2xl border border-white/[0.06] bg-[#0f0f0f] hover:bg-[#141414] hover:border-white/[0.10] transition-all duration-150 overflow-hidden"
    >
      <div className="flex items-start gap-4 px-5 py-4">
        {/* Status dot */}
        <div className="mt-0.5 shrink-0">
          <span className={cn('block w-2 h-2 rounded-full', s.dot)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-white text-sm font-semibold">{ex.workflow_name}</span>
            <StatusPill status={ex.status} />
            <TriggerPill trigger={ex.trigger_type} />
          </div>
          {inputText && (
            <p className="text-white/35 text-xs truncate mt-0.5 max-w-md">{inputText}</p>
          )}
          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            <span className="text-white/20 text-[10px] font-mono">{ex.id.slice(0, 16)}…</span>
            <span className="text-white/25 text-[10px]">{fmtTime(ex.created_at)}</span>
            {(ex.started_at) && (
              <span className="text-white/20 text-[10px]">
                {isActive ? '⏱ ' : ''}{fmtMs(ex.started_at, ex.completed_at)}
              </span>
            )}
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3 shrink-0">
          <ChevronRight size={13} className="text-white/15 group-hover:text-white/40 transition-colors" />
        </div>
      </div>
    </button>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function MonitoringPanel() {
  const [executions, setExecutions] = useState<ExecutionWithWorkflow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ExecutionWithWorkflow | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const load = useCallback(async () => {
    try {
      const data = await listAllExecutions()
      setExecutions(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!autoRefresh) return
    const iv = setInterval(load, 4000)
    return () => clearInterval(iv)
  }, [autoRefresh, load])

  if (selected) {
    return (
      <TraceView
        execution={selected}
        onBack={() => { setSelected(null); load() }}
        onRefresh={load}
      />
    )
  }

  const running   = executions.filter((e) => ['running', 'pending'].includes(e.status))
  const completed = executions.filter((e) => e.status === 'completed')
  const failed    = executions.filter((e) => ['failed', 'cancelled'].includes(e.status))
  const paused    = executions.filter((e) => e.status === 'paused')

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 w-full">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2.5">
            <Activity size={16} className="text-white/50" />
            <h1 className="text-white font-semibold text-base">Workflow Runs</h1>
            <span className="text-white/20 text-xs font-mono border border-white/[0.08] px-2 py-0.5 rounded-full">
              {executions.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAutoRefresh((v) => !v)}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] transition-colors',
                autoRefresh
                  ? 'bg-white/[0.07] text-white/70'
                  : 'text-white/30 hover:text-white/60 hover:bg-white/[0.05]',
              )}
            >
              <RefreshCw size={11} className={autoRefresh ? 'animate-spin' : ''} />
              Live
            </button>
            <button
              onClick={load}
              className="p-1.5 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/[0.05] transition-colors"
            >
              <RefreshCw size={13} />
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mb-8">
          <StatCard label="Active"    value={running.length}   color="text-blue-400"    icon={Play} />
          <StatCard label="Completed" value={completed.length} color="text-emerald-400" icon={CheckCircle2} />
          <StatCard label="Failed"    value={failed.length}    color="text-red-400"     icon={XCircle} />
          <StatCard label="Paused"    value={paused.length}    color="text-orange-400"  icon={Pause} />
        </div>

        {/* List */}
        {loading ? (
          <div className="flex justify-center py-20">
            <Loader2 size={18} className="animate-spin text-white/15" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-3 py-16">
            <AlertCircle size={16} className="text-red-400/50" />
            <p className="text-white/30 text-sm">{error}</p>
            <button onClick={load} className="text-xs text-white/40 underline underline-offset-2">Retry</button>
          </div>
        ) : executions.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/[0.07] py-20 text-center">
            <Activity size={22} className="text-white/10 mx-auto mb-3" />
            <p className="text-white/25 text-sm">No workflow runs yet</p>
            <p className="text-white/12 text-xs mt-1">Execute a workflow to see traces here</p>
          </div>
        ) : (
          <div className="space-y-2">
            {executions.map((ex) => (
              <ExRow key={ex.id} ex={ex} onClick={() => setSelected(ex)} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
