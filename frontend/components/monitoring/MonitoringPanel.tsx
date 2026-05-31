'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  Activity, RefreshCw, Loader2, AlertCircle, Clock, CheckCircle2,
  XCircle, Pause, ChevronRight, BarChart2, ArrowLeft, Play,
} from 'lucide-react'
import { listAllExecutions, getExecutionSteps, approveCheckpoint } from '@/lib/api'
import type { ExecutionWithWorkflow, WorkflowStep } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useExecutionStream } from '@/hooks/useExecutionStream'

// ── Status helpers ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    running:   { icon: Loader2,      color: 'text-blue-400 bg-blue-400/10',      label: 'Running' },
    completed: { icon: CheckCircle2, color: 'text-emerald-400 bg-emerald-400/10', label: 'Completed' },
    failed:    { icon: XCircle,      color: 'text-red-400 bg-red-400/10',         label: 'Failed' },
    pending:   { icon: Clock,        color: 'text-yellow-400 bg-yellow-400/10',   label: 'Pending' },
    cancelled: { icon: Pause,        color: 'text-white/40 bg-white/[0.06]',      label: 'Cancelled' },
  }
  const { icon: Icon, color, label } = map[status] ?? map.pending
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium', color)}>
      <Icon size={10} className={status === 'running' ? 'animate-spin' : ''} />
      {label}
    </span>
  )
}

function TriggerBadge({ trigger }: { trigger: string }) {
  const colors: Record<string, string> = {
    manual:   'text-white/40 bg-white/[0.04]',
    slack:    'text-purple-400 bg-purple-400/10',
    telegram: 'text-sky-400 bg-sky-400/10',
    chat:     'text-orange-400 bg-orange-400/10',
    schedule: 'text-teal-400 bg-teal-400/10',
  }
  return (
    <span className={cn('px-2 py-0.5 rounded text-[10px] font-mono border border-white/[0.04]', colors[trigger] ?? colors.manual)}>
      {trigger}
    </span>
  )
}

function fmtDuration(start: string | null, end: string | null): string {
  if (!start) return '—'
  const s = new Date(start).getTime()
  const e = end ? new Date(end).getTime() : Date.now()
  const ms = e - s
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

function fmtTime(ts: string | null): string {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })
}

// ── Execution Detail ───────────────────────────────────────────────────────────

function ExecutionDetail({
  execution,
  onBack,
}: {
  execution: ExecutionWithWorkflow
  onBack: () => void
}) {
  const [steps, setSteps] = useState<WorkflowStep[]>([])
  const [loadingSteps, setLoadingSteps] = useState(true)
  const [approving, setApproving] = useState(false)

  const streamState = useExecutionStream(
    execution.status === 'running' ? execution.id : null
  )

  const { nodeStatus, totalCost, totalTokens, logs, pendingApproval } = streamState

  useEffect(() => {
    getExecutionSteps(execution.id)
      .then(setSteps)
      .catch(() => {})
      .finally(() => setLoadingSteps(false))
  }, [execution.id])

  const handleApprove = async (approved: boolean) => {
    if (!pendingApproval) return
    setApproving(true)
    try {
      await approveCheckpoint(execution.id, pendingApproval.nodeId, approved)
    } finally {
      setApproving(false)
    }
  }

  const output = execution.output_data?.output || ''
  const combinedCost = totalCost || (steps.reduce((acc, s) => acc + ((s.output?.usage?.cost_usd) || 0), 0))
  const combinedTokens = totalTokens || (steps.reduce((acc, s) => acc + ((s.output?.usage?.input_tokens || 0) + (s.output?.usage?.output_tokens || 0)), 0))

  return (
    <div className="flex flex-col h-full bg-[#0d0d0d]">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-white/[0.06]">
        <button onClick={onBack} className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06]">
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-white font-semibold text-sm truncate">{execution.workflow_name}</h2>
            <StatusBadge status={execution.status} />
            <TriggerBadge trigger={execution.trigger_type} />
          </div>
          <p className="text-white/35 text-xs mt-0.5 font-mono">{execution.id.slice(0, 16)}…</p>
        </div>
        <div className="flex items-center gap-4 text-xs text-white/40 shrink-0">
          {combinedTokens > 0 && <span className="font-mono">{combinedTokens.toLocaleString()} tok</span>}
          {combinedCost > 0 && <span className="font-mono text-emerald-400/70">${combinedCost.toFixed(5)}</span>}
          <span>{fmtDuration(execution.started_at, execution.completed_at)}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {/* Approval card */}
        {pendingApproval && (
          <div className="mx-6 mt-4 rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Pause size={14} className="text-yellow-400" />
              <span className="text-yellow-400 text-sm font-medium">Awaiting approval</span>
            </div>
            {pendingApproval.preview && (
              <pre className="text-white/60 text-xs bg-white/[0.03] rounded-lg p-3 mb-3 overflow-auto max-h-32 whitespace-pre-wrap font-mono">
                {pendingApproval.preview}
              </pre>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => handleApprove(true)}
                disabled={approving}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 text-sm font-medium disabled:opacity-50"
              >
                <CheckCircle2 size={14} /> Approve
              </button>
              <button
                onClick={() => handleApprove(false)}
                disabled={approving}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 text-sm font-medium disabled:opacity-50"
              >
                <XCircle size={14} /> Reject
              </button>
            </div>
          </div>
        )}

        {/* Steps timeline */}
        <div className="px-6 py-4">
          <h3 className="text-xs font-medium text-white/40 uppercase tracking-wide mb-3">Node Timeline</h3>
          {loadingSteps ? (
            <div className="flex justify-center py-6"><Loader2 size={16} className="animate-spin text-white/20" /></div>
          ) : steps.length === 0 && logs.length === 0 ? (
            <p className="text-white/25 text-sm py-4">No steps recorded yet</p>
          ) : (
            <div className="space-y-2">
              {steps.map((step) => {
                const live = nodeStatus[step.node_id]
                const status = live || step.status
                const outputText = (step.output?.text || '').slice(0, 300)
                return (
                  <div key={step.id} className="rounded-xl border border-white/[0.06] bg-[#141414] p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <StatusBadge status={status} />
                      <span className="text-white text-sm font-medium flex-1">{step.node_id}</span>
                      <span className="text-white/30 text-xs font-mono">
                        {fmtDuration(step.started_at, step.completed_at)}
                      </span>
                      {step.output?.usage && (
                        <span className="text-white/25 text-[10px] font-mono">
                          {(step.output.usage.input_tokens || 0) + (step.output.usage.output_tokens || 0)} tok
                        </span>
                      )}
                    </div>
                    {outputText && (
                      <pre className="text-white/45 text-xs bg-white/[0.02] rounded-lg p-2 mt-2 overflow-auto max-h-24 whitespace-pre-wrap font-mono leading-relaxed">
                        {outputText}{outputText.length < (step.output?.text || '').length ? '…' : ''}
                      </pre>
                    )}
                    {step.error_message && (
                      <p className="text-red-400/70 text-xs mt-1 font-mono">{step.error_message}</p>
                    )}
                  </div>
                )
              })}
              {/* Live log entries not yet in DB */}
              {logs
                .filter((l) => !steps.some((s) => s.node_id === l.nodeId && l.kind === 'node_completed'))
                .map((log, i) => (
                  <div key={i} className="rounded-xl border border-white/[0.04] bg-[#111] p-3 opacity-70">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'w-1.5 h-1.5 rounded-full',
                        log.kind === 'node_started' ? 'bg-blue-400 animate-pulse'
                          : log.kind === 'node_completed' ? 'bg-emerald-400'
                          : 'bg-red-400'
                      )} />
                      <span className="text-white/60 text-xs font-mono">{log.nodeId}</span>
                      <span className="text-white/25 text-[10px]">{log.kind}</span>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* Output */}
        {output && (
          <div className="px-6 pb-6">
            <h3 className="text-xs font-medium text-white/40 uppercase tracking-wide mb-3">Final Output</h3>
            <div className="rounded-xl border border-white/[0.06] bg-[#141414] p-4">
              <pre className="text-white/75 text-sm whitespace-pre-wrap leading-relaxed font-mono">{output}</pre>
            </div>
          </div>
        )}

        {/* Error */}
        {execution.error_message && (
          <div className="px-6 pb-6">
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <p className="text-red-400 text-sm font-mono">{execution.error_message}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Panel ─────────────────────────────────────────────────────────────────

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

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!autoRefresh) return
    const iv = setInterval(() => {
      load()
    }, 4000)
    return () => clearInterval(iv)
  }, [autoRefresh, load])

  if (selected) {
    return (
      <ExecutionDetail
        execution={selected}
        onBack={() => { setSelected(null); load() }}
      />
    )
  }

  const running   = executions.filter((e) => e.status === 'running' || e.status === 'pending')
  const completed = executions.filter((e) => e.status === 'completed')
  const failed    = executions.filter((e) => e.status === 'failed' || e.status === 'cancelled')
  const totalCost = executions.reduce((acc, e) => acc + (((e.output_data as Record<string, unknown>)?.cost_usd as number) || 0), 0)

  return (
    <div className="flex flex-col h-full bg-[#0d0d0d] overflow-y-auto">
      <div className="max-w-4xl mx-auto px-8 py-8 w-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2.5">
            <Activity size={18} className="text-white/60" />
            <h1 className="text-white font-semibold text-lg">Monitoring</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAutoRefresh((v) => !v)}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs',
                autoRefresh ? 'bg-white/[0.08] text-white' : 'text-white/40 hover:text-white hover:bg-white/[0.06]'
              )}
            >
              <RefreshCw size={12} className={autoRefresh ? 'animate-spin' : ''} />
              Auto-refresh
            </button>
            <button
              onClick={load}
              className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06]"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Running',    value: running.length,             color: 'text-blue-400',    icon: Play },
            { label: 'Completed',  value: completed.length,           color: 'text-emerald-400', icon: CheckCircle2 },
            { label: 'Failed',     value: failed.length,              color: 'text-red-400',     icon: XCircle },
            { label: 'Total cost', value: `$${totalCost.toFixed(4)}`, color: 'text-white/60',    icon: BarChart2 },
          ].map(({ label, value, color, icon: Icon }) => (
            <div key={label} className="rounded-xl border border-white/[0.06] bg-[#141414] p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <Icon size={12} className={color} />
                <span className="text-white/40 text-xs">{label}</span>
              </div>
              <p className={cn('text-xl font-mono font-semibold', color)}>{value}</p>
            </div>
          ))}
        </div>

        {/* Executions list */}
        {loading ? (
          <div className="flex justify-center py-16"><Loader2 size={20} className="animate-spin text-white/20" /></div>
        ) : error ? (
          <div className="flex flex-col items-center gap-2 py-12">
            <AlertCircle size={18} className="text-red-400/60" />
            <p className="text-sm text-white/40">{error}</p>
            <button onClick={load} className="text-xs text-white/50 underline">Retry</button>
          </div>
        ) : executions.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/[0.08] py-16 text-center">
            <Activity size={24} className="text-white/15 mx-auto mb-3" />
            <p className="text-white/30 text-sm">No executions yet</p>
            <p className="text-white/15 text-xs mt-1">Run a workflow to see it here</p>
          </div>
        ) : (
          <div className="space-y-2">
            {executions.map((ex) => (
              <button
                key={ex.id}
                onClick={() => setSelected(ex)}
                className="w-full group flex items-center gap-3 rounded-xl border border-white/[0.06] bg-[#141414] px-4 py-3 hover:border-white/[0.12] hover:bg-[#1a1a1a] transition-colors text-left"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-white text-sm font-medium">{ex.workflow_name}</span>
                    <StatusBadge status={ex.status} />
                    <TriggerBadge trigger={ex.trigger_type} />
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-white/25 text-[11px] font-mono">{ex.id.slice(0, 12)}…</span>
                    <span className="text-white/30 text-[11px]">{fmtTime(ex.created_at)}</span>
                    {(ex.started_at || ex.completed_at) && (
                      <span className="text-white/25 text-[11px]">
                        {fmtDuration(ex.started_at, ex.completed_at)}
                      </span>
                    )}
                  </div>
                </div>
                <ChevronRight size={14} className="text-white/20 group-hover:text-white/50 flex-shrink-0" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
