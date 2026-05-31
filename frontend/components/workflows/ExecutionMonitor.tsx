'use client'

import { useMemo, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, type Edge, type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ArrowLeft, Coins, Hash, CheckCircle2, XCircle, Loader2, ShieldCheck, ThumbsUp, ThumbsDown, Pause, Square, RotateCcw } from 'lucide-react'
import { nodeTypes } from './WorkflowNodes'
import { graphToFlow } from '@/lib/workflowGraph'
import { useExecutionStream } from '@/hooks/useExecutionStream'
import { approveCheckpoint, pauseExecution, resumeExecution, terminateExecution } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Workflow } from '@/lib/types'

interface Props {
  workflow: Workflow
  executionId: string
  onBack: () => void
}

function MonitorInner({ workflow, executionId, onBack }: Props) {
  const [refreshKey, setRefreshKey] = useState(0)
  const stream = useExecutionStream(executionId, refreshKey)
  const base = useMemo(() => graphToFlow(workflow.graph_json), [workflow.id])
  const [controlling, setControlling] = useState(false)

  const handleControl = async (action: 'pause' | 'resume' | 'terminate') => {
    setControlling(true)
    try {
      if (action === 'pause') await pauseExecution(executionId)
      else if (action === 'resume') {
        await resumeExecution(executionId)
        setTimeout(() => setRefreshKey(k => k + 1), 500)
      } else await terminateExecution(executionId)
    } catch (e) {
      console.error('Control action failed:', e)
    } finally {
      setControlling(false)
    }
  }

  // Inject live status into nodes and highlight fired edges.
  const nodes: Node[] = base.nodes.map((n) => ({
    ...n,
    data: { ...n.data, status: stream.nodeStatus[n.id] ?? 'idle' },
  }))
  const edges: Edge[] = base.edges.map((e) => {
    const fired = stream.firedEdges.has(`${e.source}->${e.target}`)
    return fired
      ? { ...e, animated: true, style: { stroke: '#34d399', strokeWidth: 2.5 } }
      : { ...e, style: { ...e.style, opacity: 0.4 } }
  })

  const runningNode = Object.entries(stream.nodeStatus).find(([, s]) => s === 'running')?.[0]

  return (
    <div className="flex flex-col h-full bg-[#0d0d0d]">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06] flex-shrink-0">
        <button onClick={onBack} className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06]">
          <ArrowLeft size={16} />
        </button>
        <span className="text-white text-sm font-medium">{workflow.name}</span>
        <StatusPill status={stream.status} />
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          {stream.totalTokens > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-white/50"><Hash size={12} /> {stream.totalTokens.toLocaleString()} tok</span>
          )}
          {stream.totalCost > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-white/50"><Coins size={12} /> ${stream.totalCost.toFixed(4)}</span>
          )}
          {(stream.status === 'running' || stream.status === 'pending') && (
            <button
              onClick={() => handleControl('pause')}
              disabled={controlling}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-orange-500/15 text-orange-300 hover:bg-orange-500/25 text-xs font-medium disabled:opacity-40"
            >
              <Pause size={12} /> Pause
            </button>
          )}
          {stream.status === 'paused' && (
            <button
              onClick={() => handleControl('resume')}
              disabled={controlling}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 text-xs font-medium disabled:opacity-40"
            >
              <RotateCcw size={12} /> Resume
            </button>
          )}
          {stream.status === 'failed' && (
            <button
              onClick={() => handleControl('resume')}
              disabled={controlling}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-blue-500/15 text-blue-300 hover:bg-blue-500/25 text-xs font-medium disabled:opacity-40"
            >
              <RotateCcw size={12} /> Retry
            </button>
          )}
          {(stream.status === 'running' || stream.status === 'pending' || stream.status === 'paused') && (
            <button
              onClick={() => handleControl('terminate')}
              disabled={controlling}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-500/15 text-red-300 hover:bg-red-500/25 text-xs font-medium disabled:opacity-40"
            >
              <Square size={12} /> Stop
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Graph */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#222" gap={20} />
          </ReactFlow>
          {stream.pendingApproval && (
            <ApprovalOverlay
              approval={stream.pendingApproval}
              executionId={executionId}
              onResponse={() => {}}
            />
          )}
        </div>

        {/* Side: live log + streaming output */}
        <div className="w-[400px] flex-shrink-0 border-l border-white/[0.06] bg-[#111111] flex flex-col min-h-0">
          {/* Streaming output of the active/last node */}
          <div className="flex-1 overflow-y-auto p-4 min-h-0 border-b border-white/[0.06]">
            <p className="text-[10px] uppercase tracking-wide text-white/40 mb-2">
              {runningNode ? `${runningNode} — live output` : 'Node output'}
            </p>
            {Object.entries(stream.nodeOutputs).length === 0 ? (
              <p className="text-white/20 text-sm">Waiting for output…</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(stream.nodeOutputs).map(([nid, text]) => (
                  <div key={nid}>
                    <p className="text-[11px] text-white/40 mb-0.5">{nid}</p>
                    <p className="text-[13px] text-white/80 whitespace-pre-wrap leading-relaxed">{text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Event log */}
          <div className="h-[40%] flex-shrink-0 overflow-y-auto p-4">
            <p className="text-[10px] uppercase tracking-wide text-white/40 mb-2">Event log</p>
            <div className="space-y-1 font-mono text-[11px]">
              {stream.logs.map((l) => (
                <div key={l.id} className="flex gap-2">
                  <span className="text-white/20 flex-shrink-0">{l.ts.split(' ')[0]}</span>
                  <span className={cn('flex-1', logColor(l.kind))}>
                    {l.nodeId ? <span className="text-white/40">[{l.nodeId}] </span> : null}{l.text}
                  </span>
                </div>
              ))}
              {stream.logs.length === 0 && <p className="text-white/20">Connecting…</p>}
            </div>
          </div>
        </div>
      </div>

      {/* Final output banner */}
      {stream.status === 'completed' && stream.finalOutput && (
        <div className="border-t border-emerald-500/20 bg-emerald-500/[0.04] px-5 py-3 max-h-[28%] overflow-y-auto flex-shrink-0">
          <p className="text-[10px] uppercase tracking-wide text-emerald-400/70 mb-1.5">Final output</p>
          <p className="text-[13px] text-white/85 whitespace-pre-wrap leading-relaxed">{stream.finalOutput}</p>
        </div>
      )}
      {stream.status === 'failed' && (
        <div className="border-t border-red-500/20 bg-red-500/[0.04] px-5 py-3 flex-shrink-0">
          <p className="text-[13px] text-red-300">{stream.error ?? 'Execution failed'}</p>
        </div>
      )}
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
    running:   { cls: 'text-amber-300 bg-amber-500/10',   icon: <Loader2 size={11} className="animate-spin" />, label: 'running' },
    completed: { cls: 'text-emerald-300 bg-emerald-500/10', icon: <CheckCircle2 size={11} />,                  label: 'completed' },
    failed:    { cls: 'text-red-300 bg-red-500/10',        icon: <XCircle size={11} />,                        label: 'failed' },
    pending:   { cls: 'text-white/50 bg-white/[0.06]',     icon: <Loader2 size={11} className="animate-spin" />, label: 'pending' },
    paused:    { cls: 'text-orange-300 bg-orange-500/10',  icon: <Pause size={11} />,                          label: 'paused' },
    cancelled: { cls: 'text-white/40 bg-white/[0.06]',     icon: <XCircle size={11} />,                        label: 'cancelled' },
  }
  const s = map[status] ?? map.pending
  return (
    <span className={cn('flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium', s.cls)}>
      {s.icon} {s.label}
    </span>
  )
}

function logColor(kind: string): string {
  if (kind === 'supervisor_decision') return 'text-amber-300/90'
  if (kind === 'node_failed' || kind === 'execution_failed') return 'text-red-300/90'
  if (kind === 'execution_completed' || kind === 'node_completed') return 'text-emerald-300/80'
  if (kind === 'tool_start' || kind === 'tool_end') return 'text-sky-300/80'
  if (kind === 'output_sent' || kind === 'approval_requested') return 'text-violet-300/80'
  return 'text-white/55'
}

function ApprovalOverlay({
  approval,
  executionId,
  onResponse,
}: {
  approval: { nodeId: string; preview: string }
  executionId: string
  onResponse: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const respond = async (approved: boolean) => {
    if (busy || done) return
    setBusy(true)
    try {
      await approveCheckpoint(executionId, approval.nodeId, approved)
      setDone(true)
    } catch (e) {
      console.error(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl p-6 max-w-lg w-full mx-4 shadow-2xl">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
            <ShieldCheck size={16} className="text-amber-300" />
          </div>
          <div>
            <h3 className="text-white font-semibold text-sm">Human checkpoint</h3>
            <p className="text-white/40 text-xs">Review before the workflow continues</p>
          </div>
        </div>
        {approval.preview && (
          <div className="bg-white/[0.04] border border-white/[0.06] rounded-xl p-3.5 mb-4 text-[13px] text-white/75 leading-relaxed max-h-52 overflow-y-auto whitespace-pre-wrap font-mono">
            {approval.preview}
          </div>
        )}
        {done ? (
          <p className="text-center text-sm text-emerald-300 py-2">Response sent — workflow continuing…</p>
        ) : (
          <div className="flex gap-2.5">
            <button
              onClick={() => respond(false)}
              disabled={busy}
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm text-red-400 hover:bg-red-500/10 border border-red-500/20 transition-colors disabled:opacity-40"
            >
              <ThumbsDown size={14} /> Reject
            </button>
            <button
              onClick={() => respond(true)}
              disabled={busy}
              className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/20 transition-colors disabled:opacity-40"
            >
              {busy ? <Loader2 size={13} className="animate-spin" /> : <ThumbsUp size={14} />}
              Approve
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ExecutionMonitor(props: Props) {
  return (
    <ReactFlowProvider>
      <MonitorInner {...props} />
    </ReactFlowProvider>
  )
}
