'use client'

import { useState } from 'react'
import { Loader2, ChevronDown, Send } from 'lucide-react'
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

const ROLES = ['assistant', 'supervisor', 'researcher', 'reviewer', 'writer', 'analyst', 'support', 'planner']
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
  memory_md: string
  require_approval: boolean
  max_cost_usd: string
  avatar_emoji: string
  channel_telegram_send: boolean
  channel_telegram_receive: boolean
  channel_slack_send: boolean
  channel_slack_receive: boolean
  channel_slack_socket: boolean
}

const DEFAULT: FormState = {
  name: '', description: '', role: 'assistant', system_prompt: '',
  model: 'claude-sonnet-4-6', provider: 'anthropic',
  temperature: 0.7, max_tokens: 8096, max_iterations: 5,
  tools: [], soul_md: '', memory_md: '',
  require_approval: false, max_cost_usd: '', avatar_emoji: '🤖',
  channel_telegram_send: false,
  channel_telegram_receive: false,
  channel_slack_send: false,
  channel_slack_receive: false,
  channel_slack_socket: false,
}

function fromAgent(a: Agent): FormState {
  const g = (a.guardrails ?? {}) as Record<string, unknown>
  const cc = (a.meta?.channel_config ?? {}) as Record<string, any>
  const tg = (cc.telegram ?? {}) as Record<string, boolean>
  const sl = (cc.slack ?? {}) as Record<string, boolean>
  return {
    name: a.name, description: a.description, role: a.role, system_prompt: a.system_prompt,
    model: a.model, provider: a.provider, temperature: a.temperature,
    max_tokens: a.max_tokens, max_iterations: a.max_iterations, tools: a.tools,
    soul_md: a.soul_md ?? '', memory_md: a.memory_md ?? '',
    require_approval: Boolean(g.require_approval),
    max_cost_usd: g.max_cost_usd != null ? String(g.max_cost_usd) : '',
    avatar_emoji: (a.meta?.avatar_emoji as string) ?? '🤖',
    channel_telegram_send: tg.send ?? false,
    channel_telegram_receive: tg.receive ?? false,
    channel_slack_send: sl.send ?? false,
    channel_slack_receive: sl.receive ?? false,
    channel_slack_socket: sl.socket ?? false,
  }
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-white/50 mb-1.5">{children}</label>
}

function Input({
  value, onChange, placeholder, type = 'text',
}: {
  value: string | number
  onChange: (v: string) => void
  placeholder?: string
  type?: string
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm placeholder-white/20 outline-none focus:border-white/20 transition-colors"
    />
  )
}

function Textarea({
  value, onChange, placeholder, rows = 4, mono = false,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  rows?: number
  mono?: boolean
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className={cn(
        'w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm placeholder-white/20 outline-none focus:border-white/20 transition-colors resize-none leading-relaxed',
        mono && 'font-mono text-[12px]'
      )}
    />
  )
}

type Section = 'identity' | 'brain' | 'memory' | 'channels' | 'guardrails'

function ChannelToggle({
  label, description, value, onChange,
}: { label: string; description: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start justify-between gap-3 cursor-pointer">
      <div>
        <span className="text-[13px] text-white/75">{label}</span>
        <p className="text-[11px] text-white/30 mt-0.5">{description}</p>
      </div>
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={cn('mt-0.5 w-9 h-5 rounded-full p-0.5 transition-colors flex-shrink-0',
          value ? 'bg-emerald-500/70' : 'bg-white/[0.1]')}
      >
        <span className={cn('block w-4 h-4 rounded-full bg-white transition-transform',
          value && 'translate-x-[16px]')} />
      </button>
    </label>
  )
}

export default function AgentForm({ initial, onSubmit, onCancel }: AgentFormProps) {
  const [form, setForm] = useState<FormState>(initial ? fromAgent(initial) : DEFAULT)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [section, setSection] = useState<Section>('identity')

  const set = (key: keyof FormState) => (v: string | number | string[] | boolean) =>
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
      const guardrails: Record<string, unknown> = { require_approval: form.require_approval }
      if (form.max_cost_usd.trim()) guardrails.max_cost_usd = parseFloat(form.max_cost_usd)
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
        memory_md: form.memory_md.trim() || null,
        guardrails,
        meta: {
          avatar_emoji: form.avatar_emoji,
          channel_config: {
            telegram: { send: form.channel_telegram_send, receive: form.channel_telegram_receive },
            slack: { send: form.channel_slack_send, receive: form.channel_slack_receive, socket: form.channel_slack_socket },
          },
        },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save agent')
    } finally {
      setLoading(false)
    }
  }

  const SECTIONS: { id: Section; label: string }[] = [
    { id: 'identity', label: 'Identity' },
    { id: 'brain', label: 'Brain' },
    { id: 'memory', label: 'Memory' },
    { id: 'channels', label: 'Channels' },
    { id: 'guardrails', label: 'Guardrails' },
  ]

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
              section === s.id ? 'bg-white/[0.08] text-white' : 'text-white/30 hover:text-white/60'
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 space-y-4 pr-1">
        {section === 'identity' && (
          <>
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
                      form.avatar_emoji === e ? 'bg-white/10 ring-1 ring-white/30' : 'bg-white/[0.04] hover:bg-white/[0.08]'
                    )}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>

            <div><Label>Name *</Label><Input value={form.name} onChange={set('name')} placeholder="Research Agent" /></div>
            <div><Label>Description</Label><Input value={form.description} onChange={set('description')} placeholder="Short description — also helps a supervisor decide when to route here" /></div>

            <div>
              <Label>Role</Label>
              <div className="relative">
                <select
                  value={form.role}
                  onChange={(e) => set('role')(e.target.value)}
                  className="w-full appearance-none bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20 capitalize pr-8"
                >
                  {ROLES.map((r) => <option key={r} value={r} className="bg-[#1a1a1a] capitalize">{r}</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
              </div>
            </div>

            <div>
              <Label>System Prompt *</Label>
              <Textarea value={form.system_prompt} onChange={set('system_prompt')} rows={5}
                placeholder="You are a research specialist. Your goal is to find accurate, up-to-date information…" />
            </div>

            <div>
              <Label>SOUL.md — persona</Label>
              <p className="text-[11px] text-white/25 mb-2">A durable personality layer merged into the prompt — tone, values, boundaries.</p>
              <SoulMDEditor value={form.soul_md} onChange={set('soul_md')} />
            </div>
          </>
        )}

        {section === 'brain' && (
          <>
            <div>
              <Label>Model</Label>
              <div className="relative">
                <select
                  value={form.model}
                  onChange={(e) => handleModelChange(e.target.value)}
                  className="w-full appearance-none bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20 pr-8"
                >
                  {MODELS.map((m) => <option key={m.value} value={m.value} className="bg-[#1a1a1a]">{m.label}</option>)}
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
              <input type="range" min={0} max={1} step={0.05} value={form.temperature}
                onChange={(e) => set('temperature')(parseFloat(e.target.value))} className="w-full accent-white/60 h-1" />
            </div>

            <div>
              <Label>Max Tokens</Label>
              <div className="relative">
                <select
                  value={form.max_tokens}
                  onChange={(e) => set('max_tokens')(parseInt(e.target.value))}
                  className="w-full appearance-none bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20 pr-8"
                >
                  {[1024, 2048, 4096, 8096, 16384].map((v) => <option key={v} value={v} className="bg-[#1a1a1a]">{v.toLocaleString()}</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
              </div>
            </div>

            <div className="pt-1">
              <Label>Tools</Label>
              <p className="text-[11px] text-white/25 mb-2">The agent decides which of these to call at runtime.</p>
              <ToolSelector selected={form.tools} onChange={(v) => set('tools')(v)} />
            </div>
          </>
        )}

        {section === 'memory' && (
          <div>
            <Label>MEMORY.md — durable memory</Label>
            <p className="text-[11px] text-white/25 mb-2 leading-relaxed">
              openclaw-style persistent memory. Loaded into the prompt at the start of every run so the agent
              recalls durable facts and preferences across conversations and workflow executions.
            </p>
            <Textarea value={form.memory_md} onChange={set('memory_md')} rows={12} mono
              placeholder={'# Memory\n\n- User prefers concise, bulleted answers\n- Company tone: friendly but professional\n- Always cite sources when researching'} />
          </div>
        )}

        {section === 'channels' && (
          <div className="space-y-5">
            {/* Telegram */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-5 h-5 rounded flex items-center justify-center bg-sky-500/20">
                  <Send size={11} className="text-sky-300" />
                </div>
                <span className="text-sm font-medium text-white/80">Telegram</span>
              </div>
              <ChannelToggle
                label="Send results to Telegram"
                description="This agent's output is delivered to the bound Telegram chat."
                value={form.channel_telegram_send}
                onChange={(v) => set('channel_telegram_send')(v)}
              />
              <ChannelToggle
                label="Receive Telegram messages"
                description="Inbound Telegram messages trigger this agent via a workflow."
                value={form.channel_telegram_receive}
                onChange={(v) => set('channel_telegram_receive')(v)}
              />
            </div>

            {/* Slack */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-5 h-5 rounded flex items-center justify-center bg-violet-500/20">
                  <span className="text-[11px] text-violet-300 font-bold">#</span>
                </div>
                <span className="text-sm font-medium text-white/80">Slack</span>
              </div>
              <ChannelToggle
                label="Send results to Slack"
                description="This agent's output is posted to the bound Slack channel."
                value={form.channel_slack_send}
                onChange={(v) => set('channel_slack_send')(v)}
              />
              <ChannelToggle
                label="Receive Slack messages"
                description="@mentions or direct messages in Slack trigger this agent."
                value={form.channel_slack_receive}
                onChange={(v) => set('channel_slack_receive')(v)}
              />
              <ChannelToggle
                label="Socket Mode trigger"
                description="Use Slack Socket Mode (no public URL needed) to trigger this agent."
                value={form.channel_slack_socket}
                onChange={(v) => set('channel_slack_socket')(v)}
              />
            </div>

            <div className="rounded-lg bg-white/[0.02] border border-white/[0.04] px-3 py-2.5 text-[11px] text-white/30 leading-relaxed">
              Channel bindings are configured in <span className="text-white/50">Workflows → Channels</span>. These toggles mark which modes this agent participates in.
            </div>
          </div>
        )}

        {section === 'guardrails' && (
          <>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <Label>Max iterations</Label>
                <span className="text-xs text-white/40 font-mono">{form.max_iterations}</span>
              </div>
              <input type="range" min={1} max={15} step={1} value={form.max_iterations}
                onChange={(e) => set('max_iterations')(parseInt(e.target.value))} className="w-full accent-white/60 h-1" />
              <p className="text-[11px] text-white/20 mt-1">Caps the agent&apos;s reasoning/tool rounds per turn.</p>
            </div>

            <label className="flex items-center justify-between py-2 cursor-pointer">
              <div>
                <span className="text-sm text-white/80">Require human approval</span>
                <p className="text-[11px] text-white/25 mt-0.5">Flag sensitive output for a checkpoint before delivery.</p>
              </div>
              <button
                type="button"
                onClick={() => set('require_approval')(!form.require_approval)}
                className={cn('w-10 h-6 rounded-full p-0.5 transition-colors flex-shrink-0',
                  form.require_approval ? 'bg-emerald-500/70' : 'bg-white/[0.1]')}
              >
                <span className={cn('block w-5 h-5 rounded-full bg-white transition-transform',
                  form.require_approval && 'translate-x-[16px]')} />
              </button>
            </label>

            <div>
              <Label>Max cost per run (USD)</Label>
              <Input value={form.max_cost_usd} onChange={set('max_cost_usd')} type="number" placeholder="e.g. 0.50 (optional)" />
              <p className="text-[11px] text-white/20 mt-1">Soft budget surfaced in monitoring (advisory).</p>
            </div>
          </>
        )}
      </div>

      {error && <p className="mt-3 text-xs text-red-400 flex-shrink-0">{error}</p>}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-white/[0.06] flex-shrink-0">
        {onCancel && (
          <button type="button" onClick={onCancel}
            className="flex-1 py-2 rounded-lg text-sm text-white/40 hover:text-white/70 hover:bg-white/[0.04] transition-colors">
            Cancel
          </button>
        )}
        <button type="submit" disabled={loading}
          className="flex-1 py-2 rounded-lg text-sm bg-white text-black font-medium hover:bg-white/90 disabled:opacity-50 transition-all flex items-center justify-center gap-2">
          {loading && <Loader2 size={13} className="animate-spin" />}
          {initial ? 'Save Changes' : 'Create Agent'}
        </button>
      </div>
    </form>
  )
}
