'use client'

import { Bot, Cpu, Wrench, Pencil, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Agent } from '@/lib/types'

const PROVIDER_COLORS: Record<string, string> = {
  anthropic: 'text-orange-400',
  gemini:    'text-blue-400',
  openai:    'text-emerald-400',
}

const ROLE_COLORS: Record<string, string> = {
  researcher: 'bg-blue-500/10 text-blue-300 border-blue-500/20',
  reviewer:   'bg-amber-500/10 text-amber-300 border-amber-500/20',
  writer:     'bg-purple-500/10 text-purple-300 border-purple-500/20',
  analyst:    'bg-cyan-500/10 text-cyan-300 border-cyan-500/20',
  assistant:  'bg-white/5 text-white/50 border-white/10',
}

interface AgentCardProps {
  agent: Agent
  isSelected?: boolean
  onClick?: () => void
  onEdit?: () => void
  onDelete?: () => void
  compact?: boolean
}

export default function AgentCard({
  agent,
  isSelected,
  onClick,
  onEdit,
  onDelete,
  compact = false,
}: AgentCardProps) {
  const emoji = (agent.meta?.avatar_emoji as string) || '🤖'
  const roleClass = ROLE_COLORS[agent.role] ?? ROLE_COLORS.assistant
  const providerColor = PROVIDER_COLORS[agent.provider] ?? 'text-white/50'

  if (compact) {
    return (
      <div
        onClick={onClick}
        className={cn(
          'group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-left cursor-pointer',
          isSelected
            ? 'bg-white/[0.08] text-white'
            : 'text-[#b4b4b4] hover:bg-white/[0.05] hover:text-white'
        )}
      >
        <span className="text-base leading-none flex-shrink-0">{emoji}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{agent.name}</p>
          <p className="text-xs text-white/30 truncate capitalize">{agent.role}</p>
        </div>
        {onDelete && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="p-1 rounded text-white/25 hover:text-red-400 hover:bg-white/[0.08] opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
            title="Delete agent"
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>
    )
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        'group relative rounded-xl border p-4 cursor-pointer transition-all duration-150',
        isSelected
          ? 'bg-white/[0.06] border-white/20'
          : 'bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] hover:border-white/[0.12]'
      )}
    >
      {/* Action buttons */}
      {(onEdit || onDelete) && (
        <div className="absolute top-3 right-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {onEdit && (
            <button
              onClick={(e) => { e.stopPropagation(); onEdit() }}
              className="p-1.5 rounded-lg text-white/30 hover:text-white/70 hover:bg-white/[0.08] transition-colors"
            >
              <Pencil size={12} />
            </button>
          )}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="p-1.5 rounded-lg text-white/30 hover:text-red-400 hover:bg-white/[0.08] transition-colors"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      )}

      {/* Avatar + name */}
      <div className="flex items-start gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl bg-white/[0.06] flex items-center justify-center text-xl flex-shrink-0">
          {emoji}
        </div>
        <div className="flex-1 min-w-0 pt-0.5">
          <h3 className="text-white font-semibold text-sm truncate">{agent.name}</h3>
          <span className={cn('inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded-full border capitalize', roleClass)}>
            {agent.role}
          </span>
        </div>
      </div>

      {/* Description */}
      {agent.description && (
        <p className="text-white/40 text-xs leading-relaxed mb-3 line-clamp-2">
          {agent.description}
        </p>
      )}

      {/* Footer stats */}
      <div className="flex items-center gap-3 text-[11px] text-white/30">
        <span className={cn('flex items-center gap-1', providerColor)}>
          <Cpu size={10} />
          {agent.model.split('-').slice(0, 2).join('-')}
        </span>
        {agent.tools.length > 0 && (
          <span className="flex items-center gap-1">
            <Wrench size={10} />
            {agent.tools.length} tool{agent.tools.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>
    </div>
  )
}
