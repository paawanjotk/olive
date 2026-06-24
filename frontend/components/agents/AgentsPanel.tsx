'use client'

import { useState, useEffect, useCallback } from 'react'
import { Plus, Bot, Loader2, AlertCircle, Merge } from 'lucide-react'
import AgentForm from './AgentForm'
import { listAgents, createAgent, updateAgent, deleteAgent, deduplicateAgents } from '@/lib/api'
import type { Agent, AgentCreate } from '@/lib/types'
import { cn, plural } from '@/lib/utils'

type View = 'list' | 'create' | 'edit'

export default function AgentsPanel() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<View>('list')
  const [editing, setEditing] = useState<Agent | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setAgents(await listAgents())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async (data: AgentCreate) => {
    const created = await createAgent(data)
    setAgents((prev) => [created, ...prev])
    setView('list')
  }

  const handleUpdate = async (data: AgentCreate) => {
    if (!editing) return
    const updated = await updateAgent(editing.id, data)
    setAgents((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
    setEditing(null)
    setView('list')
  }

  const handleDelete = async (agent: Agent) => {
    if (!confirm(`Delete "${agent.name}"?`)) return
    await deleteAgent(agent.id)
    setAgents((prev) => prev.filter((a) => a.id !== agent.id))
  }

  const handleDeduplicate = async () => {
    const result = await deduplicateAgents()
    if (result.removed > 0) {
      await load()
    } else {
      alert('No duplicates found.')
    }
  }

  const startEdit = (agent: Agent) => {
    setEditing(agent)
    setView('edit')
  }

  const cancelForm = () => {
    setEditing(null)
    setView('list')
  }

  return (
    <div className="flex-1 min-w-0 flex h-full bg-[#0d0d0d]">
      {/* Left: Agent list */}
      <div className="w-72 flex-shrink-0 border-r border-white/[0.06] flex flex-col h-full bg-[#111111]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-white/[0.06] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Bot size={15} className="text-white/40" />
            <span className="text-sm font-semibold text-white">Agents</span>
            {!loading && (
              <span className="text-[11px] text-white/20 font-mono">{plural(agents.length, 'agent')}</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {agents.length > 5 && (
              <button
                onClick={handleDeduplicate}
                title="Remove duplicate agents (keeps oldest copy of each name)"
                className="p-1.5 rounded-lg text-white/25 hover:text-amber-300 hover:bg-amber-500/10 transition-colors"
              >
                <Merge size={12} />
              </button>
            )}
            <button
              onClick={() => { setEditing(null); setView('create') }}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all',
                view === 'create'
                  ? 'bg-white text-black'
                  : 'bg-white/[0.06] text-white/60 hover:bg-white/[0.10] hover:text-white'
              )}
            >
              <Plus size={12} />
              New
            </button>
          </div>
        </div>

        {/* Agent list */}
        <div className="flex-1 overflow-y-auto min-h-0 p-2 space-y-1">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={18} className="animate-spin text-white/20" />
            </div>
          ) : error ? (
            <div className="px-3 py-6 flex flex-col items-center gap-2 text-center">
              <AlertCircle size={18} className="text-red-400/60" />
              <p className="text-xs text-white/30">{error}</p>
              <button onClick={load} className="text-xs text-white/50 hover:text-white underline">Retry</button>
            </div>
          ) : agents.length === 0 ? (
            <div className="px-4 py-10 text-center">
              <p className="text-white/20 text-sm mb-1">No agents yet</p>
              <p className="text-white/10 text-xs">Create one to get started</p>
            </div>
          ) : (
            agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => startEdit(agent)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors',
                  editing?.id === agent.id
                    ? 'bg-emerald-500/[0.12] text-emerald-100'
                    : 'text-white hover:bg-white/[0.05]'
                )}
              >
                <div className="w-8 h-8 rounded-lg bg-white/[0.06] flex items-center justify-center flex-shrink-0 text-base">
                  {(agent.meta?.avatar_emoji as string) ?? '🤖'}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{agent.name}</p>
                  <p className="text-xs text-white/40 truncate">{agent.role} · {agent.model || '—'}</p>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right: Form or empty state */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {view === 'list' && (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <div className="w-14 h-14 rounded-2xl bg-white/[0.06] flex items-center justify-center mb-4">
              <Bot size={26} className="text-emerald-400" />
            </div>
            <h2 className="text-white font-semibold text-lg">Agent Studio</h2>
            <p className="mt-1.5 max-w-sm text-sm text-white/40">
              Create AI agents with custom personalities, tools, and guardrails. Select an agent to edit, or create a new one.
            </p>
            <button onClick={() => { setEditing(null); setView('create') }} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
              <Plus size={15} /> New agent
            </button>
          </div>
        )}

        {(view === 'create' || view === 'edit') && (
          <div className="flex-1 overflow-hidden flex flex-col">
            {/* Form header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] flex-shrink-0">
              <div>
                <h2 className="text-white font-semibold text-sm">
                  {view === 'create' ? 'New Agent' : `Edit — ${editing?.name}`}
                </h2>
                <p className="text-white/30 text-xs mt-0.5">
                  {view === 'create' ? 'Configure a new AI agent' : 'Update agent configuration'}
                </p>
              </div>
            </div>

            {/* Form body */}
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <AgentForm
                initial={view === 'edit' ? editing ?? undefined : undefined}
                onSubmit={view === 'create' ? handleCreate : handleUpdate}
                onCancel={cancelForm}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
