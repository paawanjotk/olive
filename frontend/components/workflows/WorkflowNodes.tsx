'use client'

import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Bot, GitBranch, ShieldCheck, Play, Flag, Loader2, Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type NodeStatus = 'idle' | 'running' | 'completed' | 'failed'

const STATUS_RING: Record<NodeStatus, string> = {
  idle: 'ring-white/[0.08]',
  running: 'ring-amber-400/80 shadow-[0_0_24px_-2px] shadow-amber-500/40',
  completed: 'ring-emerald-400/70',
  failed: 'ring-red-400/70',
}

function StatusBadge({ status }: { status: NodeStatus }) {
  if (status === 'running') return <Loader2 size={11} className="animate-spin text-amber-300" />
  if (status === 'completed') return <Check size={11} className="text-emerald-300" />
  if (status === 'failed') return <X size={11} className="text-red-300" />
  return null
}

function BaseNode({
  icon, accent, kind, data, leftHandle = true, rightHandle = true,
}: {
  icon: React.ReactNode
  accent: string
  kind: string
  data: Record<string, unknown>
  leftHandle?: boolean
  rightHandle?: boolean
}) {
  const status = (data.status as NodeStatus) ?? 'idle'
  const label = (data.label as string) ?? kind
  const description = data.description as string | undefined
  const hasAgent = Boolean(data.agentId)

  return (
    <div
      className={cn(
        'relative rounded-xl bg-[#161616] border border-white/[0.06] ring-1 px-3 py-2.5 w-[180px] transition-all',
        STATUS_RING[status]
      )}
    >
      {leftHandle && <Handle type="target" position={Position.Left} className="!bg-white/30 !w-2 !h-2 !border-0" />}
      <div className="flex items-center gap-2">
        <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0', accent)}>
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="text-[13px] font-medium text-white truncate">{label}</p>
            <StatusBadge status={status} />
          </div>
          <p className="text-[10px] uppercase tracking-wide text-white/30">{kind}</p>
        </div>
      </div>
      {description && (
        <p className="text-[11px] text-white/35 mt-1.5 leading-snug line-clamp-2">{description}</p>
      )}
      {(kind === 'agent' || kind === 'supervisor') && !hasAgent && (
        <p className="text-[10px] text-amber-400/70 mt-1">⚠ no agent assigned</p>
      )}
      {rightHandle && <Handle type="source" position={Position.Right} className="!bg-white/30 !w-2 !h-2 !border-0" />}
    </div>
  )
}

export function TriggerNode({ data }: NodeProps) {
  return <BaseNode kind="trigger" icon={<Play size={14} className="text-sky-300" />}
    accent="bg-sky-500/15" data={data as Record<string, unknown>} leftHandle={false} />
}

export function AgentNode({ data }: NodeProps) {
  return <BaseNode kind="agent" icon={<Bot size={14} className="text-violet-300" />}
    accent="bg-violet-500/15" data={data as Record<string, unknown>} />
}

export function SupervisorNode({ data }: NodeProps) {
  return <BaseNode kind="supervisor" icon={<GitBranch size={14} className="text-amber-300" />}
    accent="bg-amber-500/15" data={data as Record<string, unknown>} />
}

export function CheckpointNode({ data }: NodeProps) {
  return <BaseNode kind="checkpoint" icon={<ShieldCheck size={14} className="text-emerald-300" />}
    accent="bg-emerald-500/15" data={data as Record<string, unknown>} />
}

export function EndNode({ data }: NodeProps) {
  return <BaseNode kind="end" icon={<Flag size={14} className="text-white/50" />}
    accent="bg-white/[0.06]" data={data as Record<string, unknown>} rightHandle={false} />
}

export const nodeTypes = {
  trigger: TriggerNode,
  agent: AgentNode,
  supervisor: SupervisorNode,
  checkpoint: CheckpointNode,
  end: EndNode,
}
