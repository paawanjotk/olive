'use client'

import { useEffect, useRef, useState } from 'react'
import { executionStreamUrl, getExecution, getExecutionSteps } from '@/lib/api'
import type { ExecutionEvent, ExecutionStatus, WorkflowExecution, WorkflowStep } from '@/lib/types'

export type NodeStatus = 'idle' | 'running' | 'completed' | 'failed'

export interface LogEntry {
  id: number
  ts: string
  kind: ExecutionEvent['type']
  nodeId?: string
  text: string
}

export interface PendingApproval {
  nodeId: string
  preview: string
}

export interface PendingToolApproval {
  callId: string
  toolName: string
  toolInput: Record<string, unknown>
  nodeId: string
}

export interface StreamState {
  status: ExecutionStatus
  nodeStatus: Record<string, NodeStatus>
  firedEdges: Set<string>          // "source->target" transitions that lit up
  nodeOutputs: Record<string, string>
  logs: LogEntry[]
  totalTokens: number
  totalCost: number
  finalOutput: string
  error: string | null
  pendingApproval: PendingApproval | null
  pendingToolApproval: PendingToolApproval | null
}

const EMPTY: StreamState = {
  status: 'running',
  nodeStatus: {},
  firedEdges: new Set(),
  nodeOutputs: {},
  logs: [],
  totalTokens: 0,
  totalCost: 0,
  finalOutput: '',
  error: null,
  pendingApproval: null,
  pendingToolApproval: null,
}

const TERMINAL: ExecutionStatus[] = ['completed', 'failed', 'cancelled', 'paused']

function mapStepStatus(s: string): NodeStatus {
  if (s === 'completed') return 'completed'
  if (s === 'failed') return 'failed'
  if (s === 'running') return 'running'
  return 'idle'
}

/** Reconstruct monitor state from persisted execution + steps, so runs that
 * happened server-side (e.g. triggered from Slack/Telegram) — or that finished
 * before the monitor opened — still render fully, even though their live SSE
 * events are long gone from Redis. */
function seedFromHistory(execution: WorkflowExecution, steps: WorkflowStep[]): Partial<StreamState> {
  const nodeStatus: Record<string, NodeStatus> = {}
  const nodeOutputs: Record<string, string> = {}
  const firedEdges = new Set<string>()
  const logs: LogEntry[] = []
  let totalTokens = 0
  let totalCost = 0
  let last: string | null = null
  let seq = 0

  for (const step of steps) {
    nodeStatus[step.node_id] = mapStepStatus(step.status)
    if (step.output?.text) nodeOutputs[step.node_id] = step.output.text
    const usage = step.output?.usage
    if (usage) {
      totalTokens += (usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)
      totalCost += usage.cost_usd ?? 0
    }
    if (last && last !== step.node_id) firedEdges.add(`${last}->${step.node_id}`)
    last = step.node_id
    const ts = step.created_at ? new Date(step.created_at).toLocaleTimeString() : ''
    logs.push({ id: seq++, ts, kind: 'node_completed', nodeId: step.node_id, text: step.status })
  }

  return {
    status: execution.status,
    nodeStatus,
    nodeOutputs,
    firedEdges,
    logs,
    totalTokens,
    totalCost,
    finalOutput: execution.output_data?.output ?? '',
    error: execution.error_message,
  }
}

/** Subscribes to the workflow execution SSE stream and reduces events into
 * live state for the monitor (node statuses, fired edges, streamed output,
 * token/cost totals, event log). Seeds from persisted state first so historical
 * and externally-triggered runs render even with no live events.
 *
 * Pass a different `refreshKey` to force re-subscription (e.g. after resume). */
export function useExecutionStream(executionId: string | null, refreshKey = 0): StreamState {
  const [state, setState] = useState<StreamState>(EMPTY)
  const lastNode = useRef<string | null>(null)
  const logSeq = useRef(0)

  useEffect(() => {
    if (!executionId) return
    setState({ ...EMPTY, firedEdges: new Set() })
    lastNode.current = null
    logSeq.current = 0

    let es: EventSource | null = null
    let cancelled = false

    const log = (s: StreamState, kind: ExecutionEvent['type'], text: string, nodeId?: string): LogEntry[] =>
      [...s.logs, { id: logSeq.current++, ts: new Date().toLocaleTimeString(), kind, nodeId, text }]

    ;(async () => {
      // 1. Seed from persisted state. For terminal runs this is the whole story.
      try {
        const [execution, steps] = await Promise.all([
          getExecution(executionId),
          getExecutionSteps(executionId),
        ])
        if (cancelled) return
        const seed = seedFromHistory(execution, steps)
        setState((s) => ({ ...s, ...seed, firedEdges: seed.firedEdges ?? s.firedEdges }))
        lastNode.current = steps.length ? steps[steps.length - 1].node_id : null
        logSeq.current = seed.logs?.length ?? 0
        // Already finished — no live events will ever come; don't open SSE.
        if (TERMINAL.includes(execution.status)) return
      } catch {
        // Couldn't hydrate (e.g. race on a brand-new execution) — fall through to SSE.
      }
      if (cancelled) return

      // 2. Subscribe to live events for in-flight runs.
      const url = await executionStreamUrl(executionId)
      if (cancelled) return
      es = new EventSource(url)

      es.onmessage = (msg) => {
        let ev: ExecutionEvent
        try { ev = JSON.parse(msg.data) } catch { return }

        setState((s) => {
          const next: StreamState = {
            ...s,
            nodeStatus: { ...s.nodeStatus },
            nodeOutputs: { ...s.nodeOutputs },
            firedEdges: new Set(s.firedEdges),
          }
          switch (ev.type) {
            case 'node_started': {
              next.nodeStatus[ev.node_id] = 'running'
              if (lastNode.current && lastNode.current !== ev.node_id) {
                next.firedEdges.add(`${lastNode.current}->${ev.node_id}`)
              }
              lastNode.current = ev.node_id
              next.logs = log(s, ev.type, `${ev.label} (${ev.role}) started`, ev.node_id)
              break
            }
            case 'chunk': {
              next.nodeOutputs[ev.node_id] = (next.nodeOutputs[ev.node_id] ?? '') + ev.content
              next.logs = s.logs
              break
            }
            case 'tool_start':
              next.logs = log(s, ev.type, `→ tool ${ev.tool_name}`, ev.node_id)
              break
            case 'tool_approval_requested': {
              const tev = ev as Extract<typeof ev, { type: 'tool_approval_requested' }>
              next.pendingToolApproval = {
                callId: tev.call_id,
                toolName: tev.tool_name,
                toolInput: tev.tool_input ?? {},
                nodeId: tev.node_id ?? '',
              }
              next.logs = log(s, ev.type, `🔐 tool "${tev.tool_name}" awaiting approval`, tev.node_id)
              break
            }
            case 'tool_end':
              // Clear pending tool approval once tool resolves (approved or blocked)
              if (s.pendingToolApproval) next.pendingToolApproval = null
              next.logs = log(s, ev.type, `✓ tool ${ev.tool_name}`, ev.node_id)
              break
            case 'supervisor_decision': {
              next.firedEdges.add(`${ev.node_id}->${ev.next}`)
              next.logs = log(s, ev.type, `routes → ${ev.next}: ${ev.reason}`, ev.node_id)
              break
            }
            case 'node_completed': {
              if (s.pendingApproval?.nodeId === ev.node_id) {
                next.pendingApproval = null
              }
              next.nodeStatus[ev.node_id] = 'completed'
              if (ev.usage) {
                next.totalTokens = s.totalTokens + (ev.usage.input_tokens ?? 0) + (ev.usage.output_tokens ?? 0)
                next.totalCost = s.totalCost + (ev.usage.cost_usd ?? 0)
              }
              next.logs = log(s, ev.type, `completed`, ev.node_id)
              break
            }
            case 'node_failed': {
              if (s.pendingApproval?.nodeId === ev.node_id) {
                next.pendingApproval = null
              }
              next.nodeStatus[ev.node_id] = 'failed'
              next.logs = log(s, ev.type, `failed: ${ev.error}`, ev.node_id)
              break
            }
            case 'approval_requested':
              next.pendingApproval = { nodeId: ev.node_id ?? '', preview: (ev as any).preview ?? '' }
              next.logs = log(s, ev.type, `⏸ awaiting human approval`, ev.node_id)
              break
            case 'output_sent':
              next.logs = log(s, ev.type, `📤 sent to ${ev.platform}`)
              break
            case 'execution_completed':
              next.status = 'completed'
              next.finalOutput = ev.output
              next.logs = log(s, ev.type, `workflow complete`)
              break
            case 'execution_failed':
              next.status = 'failed'
              next.error = ev.error
              next.logs = log(s, ev.type, `workflow failed: ${ev.error}`)
              break
            case 'execution_paused':
              next.status = 'paused'
              next.logs = log(s, ev.type, `workflow paused`)
              break
            case 'execution_started':
              next.logs = log(s, ev.type, `execution started`)
              break
            default:
              next.logs = s.logs
          }
          return next
        })

        if (ev.type === 'execution_completed' || ev.type === 'execution_failed' || ev.type === 'execution_paused') {
          es?.close()
        }
      }

      es.onerror = () => { /* keepalive gaps / completion close the stream — ignore */ }
    })()

    return () => {
      cancelled = true
      es?.close()
    }
  }, [executionId, refreshKey])

  return state
}
