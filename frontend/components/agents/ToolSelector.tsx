'use client'

import { Search, Calculator, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

const ALL_TOOLS = [
  {
    name: 'web_search',
    label: 'Web Search',
    description: 'Search the web for current information and news',
    icon: Search,
  },
  {
    name: 'calculator',
    label: 'Calculator',
    description: 'Evaluate math expressions, trig, powers, sqrt',
    icon: Calculator,
  },
  {
    name: 'get_datetime',
    label: 'Date & Time',
    description: 'Get current date and time in any timezone',
    icon: Clock,
  },
]

interface ToolSelectorProps {
  selected: string[]
  onChange: (tools: string[]) => void
}

export default function ToolSelector({ selected, onChange }: ToolSelectorProps) {
  const toggle = (name: string) => {
    onChange(
      selected.includes(name)
        ? selected.filter((t) => t !== name)
        : [...selected, name]
    )
  }

  return (
    <div className="space-y-2">
      {ALL_TOOLS.map(({ name, label, description, icon: Icon }) => {
        const active = selected.includes(name)
        return (
          <button
            key={name}
            type="button"
            onClick={() => toggle(name)}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition-all duration-150',
              active
                ? 'bg-white/[0.06] border-white/20 text-white'
                : 'bg-white/[0.02] border-white/[0.06] text-white/50 hover:border-white/[0.12] hover:text-white/70'
            )}
          >
            <div className={cn(
              'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors',
              active ? 'bg-white/10' : 'bg-white/[0.04]'
            )}>
              <Icon size={13} className={active ? 'text-white/80' : 'text-white/30'} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium leading-tight">{label}</p>
              <p className="text-[11px] text-white/30 mt-0.5">{description}</p>
            </div>
            <div className={cn(
              'w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 transition-all',
              active ? 'border-white/50 bg-white/10' : 'border-white/20'
            )}>
              {active && <div className="w-2 h-2 rounded-full bg-white/70" />}
            </div>
          </button>
        )
      })}
    </div>
  )
}
