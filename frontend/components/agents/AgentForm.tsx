'use client'

import { useState } from 'react'
import { Loader2, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import ToolSelector from './ToolSelector'
import SoulMDEditor from './SoulMDEditor'
import type { Agent, AgentCreate } from '@/lib/types'

const MODELS = [
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6', provider: 'anthropic' },
  { value: 'claude-opus-4-7',   label: 'Claude Opus 4.7',   provider: 'anthropic' },
  { value: 'claude-haiku-4-5',  label: 'Claude Haiku 4.5',  provider: 'anthropic' },
  { value: 'gemini-2.5-flash',  label: 'Gemini 2.5 Flash',  provider: 'gemini' },
  { value: 'gpt-4o',            label: 'GPT-4o',            provider: 'openai' },
  { value: 'gpt-4o-mini',       label: 'GPT-4o Mini',       provider: 'openai' },
]

const ROLES = ['assistant', 'researcher', 'reviewer', 'writer', 'analyst', 'planner']

const EMOJIS = ['🤖', '🔍', '✍️', '🧠', '📊', '🎯', '⚡', '🛠️', '🌐', '📝', '🔬', '💡']

interface AgentFormProps {
  initial?: Agent
  onSubmit: (data: AgentCreate) => Promise<void>
  onCancel?: () => void
}

interface FormState {
  name: string
  description: string
  role: string
  system_prompt: string
  model: string
  provider: string
  temperature: number
  max_tokens: number
  max_iterations: number
  tools: string[]
  soul_md: string
  avatar_emoji: string
}

const DEFAULT: FormState = {
  name: '',
  description: '',
  role: 'assistant',
  system_prompt: '',
  model: 'claude-sonnet-4-6',
  provider: 'anthropic',
  temperature: 0.7,
  max_tokens: 8096,
  max_iterations: 5,
  tools: [],
  soul_md: '',
  avatar_emoji: '🤖',
}

function fromAgent(a: Agent): FormState {
  return {
    name: a.name,
    description: a.description,
    role: a.role,
    system_prompt: a.system_prompt,
    model: a.model,
    provider: a.provider,
    temperature: a.temperature,
    max_tokens: a.max_tokens,
    max_iterations: a.max_iterations,
    tools: a.tools,
    soul_md: a.soul_md ?? '',
    avatar_emoji: (a.meta?.avatar_emoji as string) ?? '🤖',
  }
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-white/50 mb-1.5">{children}</label>
}

function Input({
  value,
  onChange,
  placeholder,
  type = 'text',
  step,
  min,
  max,
  className,
}: {
  value: string | number
  onChange: (v: string) => void
  placeholder?: string
  type?: string
  step?: string
  min?: number
  max?: number
  className?: string
}) {
  return (
    <input
      type={type}
      step={step}
      min={min}
      max={max}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cn(
        'w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm',
        'placeholder-white/20 outline-none focus:border-white/20 transition-colors',
        className
      )}
    />
  )
}

function Textarea({
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  rows?: number
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm placeholder-white/20 outline-none focus:border-white/20 transition-colors resize-none leading-relaxed"
    />
  )
}

export default function AgentForm({ initial, onSubmit, onCancel }: AgentFormProps) {
  const [form, setForm] = useState<FormState>(initial ? fromAgent(initial) : DEFAULT)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [section, setSection] = useState<'identity' | 'intelligence' | 'tools' | 'soul'>('identity')

  const set = (key: keyof FormState) => (v: string | number | string[]) =>
    setForm((prev) => ({ ...prev, [key]: v }))

  const handleModelChange = (model: string) => {
    const m = MODELS.find((m) => m.value === model)
    setForm((prev) => ({ ...prev, model, provider: m?.provider ?? prev.provider }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.system_prompt.trim()) {
      setError('Name and system prompt are required.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      await onSubmit({
        name: form.name.trim(),
        description: form.description.trim(),
        role: form.role,
        system_prompt: form.system_prompt.trim(),
        model: form.model,
        provider: form.provider,
        temperature: form.temperature,
        max_tokens: form.max_tokens,
        max_iterations: form.max_iterations,
        tools: form.tools,
        soul_md: form.soul_md.trim() || null,
        meta: { avatar_emoji: form.avatar_emoji },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save agent')
    } finally {
      setLoading(false)
    }
  }

  const SECTIONS = [
    { id: 'identity',     label: 'Identity' },
    { id: 'intelligence', label: 'Intelligence' },
    { id: 'tools',        label: 'Tools' },
    { id: 'soul',         label: 'Soul' },
  ] as const

  return (
    <form onSubmit={handleSubmit} className="flex flex-col h-full">
      {/* Section tabs */}
      <div className="flex gap-0.5 mb-5 bg-white/[0.03] rounded-lg p-1 flex-shrink-0">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSection(s.id)}
            className={cn(
              'flex-1 py-1.5 text-xs font-medium rounded-md transition-all',
              section === s.id
                ? 'bg-white/[0.08] text-white'
                : 'text-white/30 hover:text-white/60'
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Scrollable form body */}
      <div className="flex-1 overflow-y-auto min-h-0 space-y-4 pr-1">

        {section === 'identity' && (
          <>
            {/* Avatar emoji picker */}
            <div>
              <Label>Avatar</Label>
              <div className="flex flex-wrap gap-2">
                {EMOJIS.map((e) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => set('avatar_emoji')(e)}
                    className={cn(
                      'w-9 h-9 rounded-lg text-lg flex items-center justify-center transition-all',
                      form.avatar_emoji === e
                        ? 'bg-white/10 ring-1 ring-white/30'
                        : 'bg-white/[0.04] hover:bg-white/[0.08]'
                    )}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label>Name *</Label>
              <Input value={form.name} onChange={set('name')} placeholder="Research Agent" />
            </div>

            <div>
              <Label>Description</Label>
              <Input value={form.description} onChange={set('description')} placeholder="Short description of what this agent does" />
            </div>

            <div>
              <Label>Role</Label>
              <div className="relative">
                <select
                  value={form.role}
                  onChange={(e) => set('role')(e.target.value)}
                  className="w-full appearance-none bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20 transition-colors capitalize pr-8"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r} className="bg-[#1a1a1a] capitalize">{r}</option>
                  ))}
                </select>
                <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
              </div>
            </div>

            <div>
              <Label>System Prompt *</Label>
              <Textarea
                value={form.system_prompt}
                onChange={set('system_prompt')}
                placeholder="You are a research specialist. Your goal is to find accurate, up-to-date information from reliable sources..."
                rows={6}
              />
            </div>
          </>
        )}

        {section === 'intelligence' && (
          <>
            <div>
              <Label>Model</Label>
              <div className="relative">
                <select
                  value={form.model}
                  onChange={(e) => handleModelChange(e.target.value)}
                  className="w-full appearance-none bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20 transition-colors pr-8"
                >
                  {MODELS.map((m) => (
                    <option key={m.value} value={m.value} className="bg-[#1a1a1a]">{m.label}</option>
                  ))}
                </select>
                <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
              </div>
              <p className="text-[11px] text-white/20 mt-1">Provider: {form.provider}</p>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <Label>Temperature</Label>
                <span className="text-xs text-white/40 font-mono">{form.temperature}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={form.temperature}
                onChange={(e) => set('temperature')(parseFloat(e.target.value))}
                className="w-full accent-white/60 h-1"
              />
              <div className="flex justify-between text-[10px] text-white/20 mt-1">
                <span>Precise</span>
                <span>Creative</span>
              </div>
            </div>

            <div>
              <Label>Max Tokens</Label>
              <div className="relative">
                <select
                  value={form.max_tokens}
                  onChange={(e) => set('max_tokens')(parseInt(e.target.value))}
                  className="w-full appearance-none bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20 transition-colors pr-8"
                >
                  {[1024, 2048, 4096, 8096, 16384].map((v) => (
                    <option key={v} value={v} className="bg-[#1a1a1a]">{v.toLocaleString()}</option>
                  ))}
                </select>
                <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <Label>Max Tool Iterations</Label>
                <span className="text-xs text-white/40 font-mono">{form.max_iterations}</span>
              </div>
              <input
                type="range"
                min={1}
                max={15}
                step={1}
                value={form.max_iterations}
                onChange={(e) => set('max_iterations')(parseInt(e.target.value))}
                className="w-full accent-white/60 h-1"
              />
              <div className="flex justify-between text-[10px] text-white/20 mt-1">
                <span>1</span>
                <span>15</span>
              </div>
            </div>
          </>
        )}

        {section === 'tools' && (
          <div>
            <p className="text-xs text-white/30 mb-3">Select which tools this agent can invoke during a conversation.</p>
            <ToolSelector selected={form.tools} onChange={(v) => set('tools')(v)} />
          </div>
        )}

        {section === 'soul' && (
          <div>
            <p className="text-xs text-white/30 mb-3">
              Soul gives the agent a persistent personality, philosophy, and behavioral guidelines beyond the system prompt.
            </p>
            <SoulMDEditor value={form.soul_md} onChange={set('soul_md')} />
          </div>
        )}
      </div>

      {/* Footer */}
      {error && (
        <p className="mt-3 text-xs text-red-400 flex-shrink-0">{error}</p>
      )}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-white/[0.06] flex-shrink-0">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 py-2 rounded-lg text-sm text-white/40 hover:text-white/70 hover:bg-white/[0.04] transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={loading}
          className="flex-1 py-2 rounded-lg text-sm bg-white text-black font-medium hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
        >
          {loading && <Loader2 size={13} className="animate-spin" />}
          {initial ? 'Save Changes' : 'Create Agent'}
        </button>
      </div>
    </form>
  )
}
