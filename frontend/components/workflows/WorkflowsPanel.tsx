'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Workflow as WorkflowIcon, Plus, Loader2, AlertCircle, Play, Trash2,
  Sparkles, Send, History,
} from 'lucide-react'
import {
  listWorkflows, listTemplates, cloneTemplate, createWorkflow, updateWorkflow,
  deleteWorkflow, executeWorkflow, listAgents,
  listChannelBindings, createChannelBinding, deleteChannelBinding,
} from '@/lib/api'
import type {
  Workflow, WorkflowTemplate, Agent, GraphJson, ChannelBinding,
} from '@/lib/types'
import { cn } from '@/lib/utils'
import WorkflowBuilder from './WorkflowBuilder'
import ExecutionMonitor from './ExecutionMonitor'

type View =
  | { name: 'list' }
  | { name: 'builder'; workflow: Workflow }
  | { name: 'monitor'; workflow: Workflow; executionId: string }

const EMPTY_GRAPH: GraphJson = {
  nodes: [
    { id: 'trigger', type: 'trigger', position: { x: 0, y: 120 }, data: { label: 'Manual input' } },
    { id: 'end', type: 'end', position: { x: 600, y: 120 }, data: { label: 'End' } },
  ],
  edges: [],
}

export default function WorkflowsPanel() {
  const [view, setView] = useState<View>({ name: 'list' })
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [bindings, setBindings] = useState<ChannelBinding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [wf, tpl, ag, ch] = await Promise.all([
        listWorkflows(), listTemplates(), listAgents(), listChannelBindings(),
      ])
      setWorkflows(wf); setTemplates(tpl); setAgents(ag); setBindings(ch)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load workflows')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Which workflow currently "owns" each Slack channel id — used to warn about
  // collisions in the builder (a channel maps to exactly one workflow).
  const slackChannelOwners = useMemo(() => {
    const m: Record<string, { id: string; name: string }> = {}
    for (const w of workflows) {
      const slack = w.graph_json?.channel_config?.slack
      if (slack?.enabled && slack?.channel_id) {
        m[slack.channel_id] = { id: w.id, name: w.name }
      }
    }
    return m
  }, [workflows])

  const handleClone = async (key: string) => {
    const wf = await cloneTemplate(key)
    setWorkflows((p) => [wf, ...p])
    setAgents(await listAgents())  // template created new agents
    setView({ name: 'builder', workflow: wf })
  }

  const handleNew = async () => {
    const wf = await createWorkflow({ name: 'Untitled workflow', graph_json: EMPTY_GRAPH })
    setWorkflows((p) => [wf, ...p])
    setView({ name: 'builder', workflow: wf })
  }

  const handleSave = async (graphJson: GraphJson, name: string, workflow: Workflow) => {
    const updated = await updateWorkflow(workflow.id, { graph_json: graphJson, name })
    setWorkflows((p) => p.map((w) => (w.id === updated.id ? updated : w)))
    setView({ name: 'builder', workflow: updated })
  }

  const handleRun = async (workflow: Workflow, input: string) => {
    const ex = await executeWorkflow(workflow.id, input)
    setView({ name: 'monitor', workflow, executionId: ex.id })
  }

  const handleDelete = async (wf: Workflow) => {
    if (!confirm(`Delete "${wf.name}"?`)) return
    await deleteWorkflow(wf.id)
    setWorkflows((p) => p.filter((w) => w.id !== wf.id))
  }

  if (view.name === 'builder') {
    return (
      <div className="flex-1 h-full">
        <WorkflowBuilder
          workflow={view.workflow}
          agents={agents}
          channelOwners={slackChannelOwners}
          onSave={(g, n) => handleSave(g, n, view.workflow)}
          onRun={(input) => handleRun(view.workflow, input)}
          onBack={() => { setView({ name: 'list' }); load() }}
          onOpenExecution={(executionId) => setView({ name: 'monitor', workflow: view.workflow, executionId })}
        />
      </div>
    )
  }

  if (view.name === 'monitor') {
    return (
      <div className="flex-1 h-full">
        <ExecutionMonitor
          workflow={view.workflow}
          executionId={view.executionId}
          onBack={() => setView({ name: 'builder', workflow: view.workflow })}
        />
      </div>
    )
  }

  return (
    <div className="flex-1 h-full overflow-y-auto bg-[#0d0d0d]">
      <div className="max-w-4xl mx-auto px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2.5">
            <WorkflowIcon size={20} className="text-white/60" />
            <h1 className="text-white font-semibold text-lg">Workflows</h1>
          </div>
          <button
            onClick={handleNew}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-white text-black font-medium hover:bg-white/90"
          >
            <Plus size={14} /> New workflow
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-16"><Loader2 size={20} className="animate-spin text-white/20" /></div>
        ) : error ? (
          <div className="flex flex-col items-center gap-2 py-12">
            <AlertCircle size={18} className="text-red-400/60" />
            <p className="text-sm text-white/40">{error}</p>
            <button onClick={load} className="text-xs text-white/50 underline">Retry</button>
          </div>
        ) : (
          <>
            {/* Templates */}
            <section className="mb-8">
              <div className="flex items-center gap-1.5 mb-3">
                <Sparkles size={13} className="text-white/40" />
                <h2 className="text-xs font-medium text-white/50 uppercase tracking-wide">Start from a template</h2>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {templates.map((t) => (
                  <div key={t.key} className="rounded-xl border border-white/[0.06] bg-[#141414] p-4 hover:border-white/[0.12] transition-colors">
                    <p className="text-white text-sm font-medium">{t.name}</p>
                    <p className="text-white/35 text-xs mt-1 leading-relaxed h-8 line-clamp-2">{t.description}</p>
                    <div className="flex items-center justify-between mt-3">
                      <span className="text-[11px] text-white/25">{t.agent_count} agents</span>
                      <button
                        onClick={() => handleClone(t.key)}
                        className="text-xs px-2.5 py-1 rounded-lg bg-white/[0.06] text-white/70 hover:bg-white/[0.12] hover:text-white transition-colors"
                      >
                        Use template
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* My workflows */}
            <section className="mb-8">
              <h2 className="text-xs font-medium text-white/50 uppercase tracking-wide mb-3">My workflows</h2>
              {workflows.length === 0 ? (
                <div className="rounded-xl border border-dashed border-white/[0.08] py-10 text-center">
                  <p className="text-white/30 text-sm">No workflows yet</p>
                  <p className="text-white/15 text-xs mt-1">Clone a template or create one from scratch</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {workflows.map((wf) => (
                    <div key={wf.id} className="group flex items-center gap-3 rounded-xl border border-white/[0.06] bg-[#141414] px-4 py-3 hover:border-white/[0.12] transition-colors">
                      <button className="flex-1 text-left min-w-0" onClick={() => setView({ name: 'builder', workflow: wf })}>
                        <p className="text-white text-sm font-medium truncate">{wf.name}</p>
                        <p className="text-white/30 text-xs truncate">
                          {(wf.graph_json.nodes ?? []).length} nodes · {(wf.graph_json.edges ?? []).length} edges
                        </p>
                      </button>
                      <button
                        onClick={() => setView({ name: 'builder', workflow: wf })}
                        className="text-xs px-2.5 py-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/[0.06]"
                      >
                        Open
                      </button>
                      <button
                        onClick={() => handleDelete(wf)}
                        className="p-1.5 rounded-lg text-white/25 hover:text-red-400 hover:bg-white/[0.06] opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Telegram channels */}
            <TelegramSection
              workflows={workflows}
              bindings={bindings}
              onChange={async () => setBindings(await listChannelBindings())}
            />

            {/* Slack — configured per-workflow in the builder's Channels panel */}
            <div className="mt-6 rounded-xl border border-white/[0.04] bg-[#141414] p-4">
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-white/40 text-sm font-bold">#</span>
                <h2 className="text-xs font-medium text-white/50 uppercase tracking-wide">Slack</h2>
              </div>
              <p className="text-white/30 text-xs leading-relaxed">
                Open any workflow → click <span className="text-white/50">Channels</span> in the toolbar → enable Slack and paste your channel ID.
                The socket listener starts automatically with the backend — no extra process needed.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function TelegramSection({
  workflows, bindings, onChange,
}: { workflows: Workflow[]; bindings: ChannelBinding[]; onChange: () => Promise<void> }) {
  const [chatId, setChatId] = useState('')
  const [workflowId, setWorkflowId] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const telegramBindings = bindings.filter((b) => b.platform === 'telegram')

  const bind = async () => {
    if (!chatId.trim() || !workflowId) return
    setBusy(true); setErr(null)
    try {
      await createChannelBinding({ platform: 'telegram', external_id: chatId.trim(), workflow_id: workflowId })
      setChatId(''); setWorkflowId('')
      await onChange()
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed to bind')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="flex items-center gap-1.5 mb-3">
        <Send size={13} className="text-white/40" />
        <h2 className="text-xs font-medium text-white/50 uppercase tracking-wide">Telegram channels</h2>
      </div>
      <div className="rounded-xl border border-white/[0.06] bg-[#141414] p-4">
        <p className="text-white/35 text-xs mb-3 leading-relaxed">
          Connect a Telegram chat to a workflow. Message your bot, send <span className="text-white/55 font-mono">/start</span>,
          then bind the chat id shown by the bot here. Inbound messages run the workflow and the reply is sent back.
        </p>
        <div className="flex gap-2">
          <input
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            placeholder="Telegram chat id"
            className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20"
          />
          <select
            value={workflowId}
            onChange={(e) => setWorkflowId(e.target.value)}
            className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20"
          >
            <option value="" className="bg-[#1a1a1a]">— select workflow —</option>
            {workflows.map((w) => (
              <option key={w.id} value={w.id} className="bg-[#1a1a1a]">{w.name}</option>
            ))}
          </select>
          <button
            onClick={bind}
            disabled={busy || !chatId.trim() || !workflowId}
            className="px-3 py-2 rounded-lg text-sm bg-white/[0.06] text-white/70 hover:bg-white/[0.12] hover:text-white disabled:opacity-40"
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : 'Bind'}
          </button>
        </div>
        {err && <p className="text-xs text-red-400 mt-2">{err}</p>}

        {telegramBindings.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {telegramBindings.map((b) => {
              const wf = workflows.find((w) => w.id === b.workflow_id)
              return (
                <div key={b.id} className="flex items-center gap-2 text-xs text-white/50">
                  <span className="font-mono text-white/40">{b.platform}:{b.external_id}</span>
                  <span className="text-white/20">→</span>
                  <span className="flex-1 truncate">{wf?.name ?? 'unknown workflow'}</span>
                  <button
                    onClick={async () => { await deleteChannelBinding(b.id); await onChange() }}
                    className="p-1 rounded text-white/25 hover:text-red-400"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}

function SlackSection({
  workflows, bindings, onChange,
}: { workflows: Workflow[]; bindings: ChannelBinding[]; onChange: () => Promise<void> }) {
  const [channelId, setChannelId] = useState('')
  const [workflowId, setWorkflowId] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const slackBindings = bindings.filter((b) => b.platform === 'slack')

  const bind = async () => {
    if (!channelId.trim() || !workflowId) return
    setBusy(true); setErr(null)
    try {
      await createChannelBinding({ platform: 'slack', external_id: channelId.trim(), workflow_id: workflowId })
      setChannelId(''); setWorkflowId('')
      await onChange()
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed to bind')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mt-6">
      <div className="flex items-center gap-1.5 mb-3">
        <span className="text-white/40 text-sm font-bold">#</span>
        <h2 className="text-xs font-medium text-white/50 uppercase tracking-wide">Slack channels</h2>
      </div>
      <div className="rounded-xl border border-white/[0.06] bg-[#141414] p-4">
        <p className="text-white/35 text-xs mb-3 leading-relaxed">
          Connect a Slack channel to a workflow. Copy the channel ID from Slack (right-click channel → Copy link, the ID is the last segment like <span className="text-white/55 font-mono">C0123ABCDEF</span>).
          When the bot is @mentioned, the workflow runs and replies in the thread.
        </p>
        <div className="flex gap-2">
          <input
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
            placeholder="Slack channel ID (C...)"
            className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20"
          />
          <select
            value={workflowId}
            onChange={(e) => setWorkflowId(e.target.value)}
            className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20"
          >
            <option value="" className="bg-[#1a1a1a]">— select workflow —</option>
            {workflows.map((w) => (
              <option key={w.id} value={w.id} className="bg-[#1a1a1a]">{w.name}</option>
            ))}
          </select>
          <button
            onClick={bind}
            disabled={busy || !channelId.trim() || !workflowId}
            className="px-3 py-2 rounded-lg text-sm bg-white/[0.06] text-white/70 hover:bg-white/[0.12] hover:text-white disabled:opacity-40"
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : 'Bind'}
          </button>
        </div>
        {err && <p className="text-xs text-red-400 mt-2">{err}</p>}
        {slackBindings.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {slackBindings.map((b) => {
              const wf = workflows.find((w) => w.id === b.workflow_id)
              return (
                <div key={b.id} className="flex items-center gap-2 text-xs text-white/50">
                  <span className="font-mono text-white/40">{b.platform}:{b.external_id}</span>
                  <span className="text-white/20">→</span>
                  <span className="flex-1 truncate">{wf?.name ?? 'unknown workflow'}</span>
                  <button
                    onClick={async () => { await deleteChannelBinding(b.id); await onChange() }}
                    className="p-1 rounded text-white/25 hover:text-red-400"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}
