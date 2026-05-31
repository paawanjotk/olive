'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState,
  type Connection, type Edge, type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  ArrowLeft, Bot, GitBranch, ShieldCheck, Save, Play, Trash2, Loader2, Radio,
  History, CheckCircle2, XCircle, Clock, CalendarClock, Plus, RefreshCw,
} from 'lucide-react'
import { nodeTypes } from './WorkflowNodes'
import { styleEdges, graphToFlow, flowToGraph } from '@/lib/workflowGraph'
import { listExecutions, listSchedules, createSchedule, deleteSchedule } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Agent, Workflow, WorkflowExecution, WorkflowSchedule } from '@/lib/types'

interface Props {
  workflow: Workflow
  agents: Agent[]
  onSave: (graphJson: ReturnType<typeof flowToGraph>, name: string) => Promise<void>
  onRun: (input: string) => void
  onBack: () => void
  onOpenExecution?: (executionId: string) => void
  channelOwners?: Record<string, { id: string; name: string }>
}

let _seq = 0
const newId = (t: string) => `${t}_${Date.now().toString(36)}_${_seq++}`

function BuilderInner({ workflow, agents, onSave, onRun, onBack, onOpenExecution, channelOwners }: Props) {
  const initial = useMemo(() => graphToFlow(workflow.graph_json), [workflow.id])
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges)
  const [name, setName] = useState(workflow.name)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const [runOpen, setRunOpen] = useState(false)
  const [runInput, setRunInput] = useState('')
  const [inspectorTab, setInspectorTab] = useState<'node' | 'channels' | 'runs'>('node')
  const [channelConfig, setChannelConfig] = useState<any>(workflow.graph_json.channel_config ?? {})

  // Warn if this workflow's Slack channel is already claimed by a different one.
  const slackChannelId = channelConfig.slack?.channel_id
  const channelConflict =
    slackChannelId && channelOwners?.[slackChannelId] && channelOwners[slackChannelId].id !== workflow.id
      ? channelOwners[slackChannelId].name
      : null

  const onConnect = useCallback(
    (c: Connection) => setEdges((eds) => styleEdges(nodes, addEdge(c, eds))),
    [nodes, setEdges]
  )

  const reStyle = useCallback(
    (nextNodes: Node[]) => setEdges((eds) => styleEdges(nextNodes, eds)),
    [setEdges]
  )

  const addNode = (type: 'agent' | 'supervisor' | 'checkpoint') => {
    const id = newId(type)
    const label = type === 'agent' ? 'New Agent' : type === 'supervisor' ? 'New Supervisor' : 'Human checkpoint'
    const node: Node = {
      id, type,
      position: { x: 360 + Math.random() * 120, y: 120 + Math.random() * 160 },
      data: { label, description: '' },
    }
    setNodes((nds) => {
      const next = [...nds, node]
      reStyle(next)
      return next
    })
    setSelectedId(id)
  }

  const selected = nodes.find((n) => n.id === selectedId) ?? null

  const updateSelected = (patch: Record<string, unknown>) => {
    setNodes((nds) => {
      const next = nds.map((n) =>
        n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n
      )
      reStyle(next)
      return next
    })
  }

  const deleteSelected = () => {
    if (!selectedId) return
    setNodes((nds) => nds.filter((n) => n.id !== selectedId))
    setEdges((eds) => eds.filter((e) => e.source !== selectedId && e.target !== selectedId))
    setSelectedId(null)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const graph = flowToGraph(nodes, edges)
      graph.channel_config = channelConfig
      await onSave(graph, name.trim() || 'Untitled workflow')
      setSavedAt(new Date().toLocaleTimeString())
    } finally {
      setSaving(false)
    }
  }

  const editable = selected && (selected.type === 'agent' || selected.type === 'supervisor')

  return (
    <div className="flex flex-col h-full bg-[#0d0d0d]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06] flex-shrink-0">
        <button onClick={onBack} className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06]">
          <ArrowLeft size={16} />
        </button>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="bg-transparent text-white text-sm font-medium outline-none border-b border-transparent focus:border-white/20 min-w-[160px]"
        />
        <div className="flex items-center gap-1.5 ml-2">
          <PaletteBtn icon={<Bot size={13} />} label="Agent" onClick={() => addNode('agent')} />
          <PaletteBtn icon={<GitBranch size={13} />} label="Supervisor" onClick={() => addNode('supervisor')} />
          <PaletteBtn icon={<ShieldCheck size={13} />} label="Checkpoint" onClick={() => addNode('checkpoint')} />
          <div className="w-px h-5 bg-white/[0.08] mx-1" />
          <button
            onClick={() => setInspectorTab(t => t === 'channels' ? 'node' : 'channels')}
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors',
              inspectorTab === 'channels'
                ? 'bg-white/[0.10] text-white'
                : 'text-white/50 hover:text-white bg-white/[0.03] hover:bg-white/[0.08]'
            )}
          >
            <Radio size={13} /> Channels
          </button>
          <button
            onClick={() => setInspectorTab(t => t === 'runs' ? 'node' : 'runs')}
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors',
              inspectorTab === 'runs'
                ? 'bg-white/[0.10] text-white'
                : 'text-white/50 hover:text-white bg-white/[0.03] hover:bg-white/[0.08]'
            )}
          >
            <History size={13} /> Runs
          </button>
        </div>
        <div className="flex-1" />
        {savedAt && <span className="text-[11px] text-white/25">saved {savedAt}</span>}
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/[0.06] text-white/70 hover:bg-white/[0.10] hover:text-white disabled:opacity-50"
        >
          {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Save
        </button>
        <button
          onClick={() => setRunOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white text-black font-medium hover:bg-white/90"
        >
          <Play size={12} /> Run
        </button>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Canvas */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, n) => setSelectedId(n.id)}
            onPaneClick={() => setSelectedId(null)}
            nodeTypes={nodeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ style: { stroke: 'rgba(255,255,255,0.25)' } }}
          >
            <Background color="#222" gap={20} />
            <Controls className="!bg-[#161616] !border-white/10 [&_button]:!bg-[#161616] [&_button]:!border-white/10 [&_button]:!fill-white/60" />
            <MiniMap
              pannable zoomable
              className="!bg-[#111]"
              nodeColor={(n) => ({
                trigger: '#38bdf8', agent: '#a78bfa', supervisor: '#fbbf24',
                checkpoint: '#34d399', end: '#666',
              } as Record<string, string>)[n.type ?? 'agent'] ?? '#666'}
              maskColor="rgba(0,0,0,0.6)"
            />
            <LegendPanel />
          </ReactFlow>
        </div>

        {/* Inspector */}
        <div className="w-72 flex-shrink-0 border-l border-white/[0.06] bg-[#111111] p-4 overflow-y-auto">
          {inspectorTab === 'runs' ? (
            <RunsPanel workflowId={workflow.id} onOpen={onOpenExecution} />
          ) : inspectorTab === 'channels' ? (
            <ChannelsPanel config={channelConfig} onChange={setChannelConfig} conflict={channelConflict} />
          ) : !selected ? (
            <div className="text-center pt-10">
              <p className="text-white/30 text-sm">Select a node to configure it</p>
              <p className="text-white/15 text-xs mt-2 leading-relaxed">
                Drag from a node&apos;s right handle to another node&apos;s left handle to connect them.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-wide text-white/40">{selected.type}</span>
                {selected.type !== 'trigger' && selected.type !== 'end' && (
                  <button onClick={deleteSelected} className="p-1 rounded text-white/30 hover:text-red-400">
                    <Trash2 size={13} />
                  </button>
                )}
              </div>

              <Field label="Label">
                <input
                  value={(selected.data.label as string) ?? ''}
                  onChange={(e) => updateSelected({ label: e.target.value })}
                  className="builder-input"
                />
              </Field>

              <Field label="Description">
                <textarea
                  value={(selected.data.description as string) ?? ''}
                  onChange={(e) => updateSelected({ description: e.target.value })}
                  rows={3}
                  className="builder-input resize-none"
                  placeholder="Helps the supervisor decide when to route here"
                />
              </Field>

              {selected.type === 'trigger' && (
                <TriggerSource
                  config={channelConfig}
                  onChange={setChannelConfig}
                  onLabel={(label) => updateSelected({ label })}
                  onOpenChannels={() => setInspectorTab('channels')}
                  conflict={channelConflict}
                  workflowId={workflow.id}
                />
              )}

              {selected.type === 'checkpoint' && (() => {
                const approvalMode = (selected.data.approval_mode as string) ?? 'web'
                const needsSlack = approvalMode === 'slack' || approvalMode === 'both'
                return (
                  <>
                    <Field label="Approval via">
                      <select
                        value={approvalMode}
                        onChange={(e) => updateSelected({ approval_mode: e.target.value })}
                        className="builder-input"
                      >
                        <option value="web" className="bg-[#1a1a1a]">Web UI — Approve/Reject buttons</option>
                        <option value="slack" className="bg-[#1a1a1a]">Slack — interactive buttons</option>
                        <option value="both" className="bg-[#1a1a1a]">Both — whichever responds first</option>
                      </select>
                      <p className="text-[10px] text-white/30 mt-1.5 leading-snug">
                        Web shows an Approve/Reject overlay in the run monitor. Slack posts a Block Kit
                        card with Approve/Reject buttons — works even for manually triggered runs.
                        The run pauses up to 5 min, then auto-approves.
                      </p>
                    </Field>
                    {needsSlack && (
                      <Field label="Slack channel ID">
                        <input
                          value={(selected.data.slack_channel_id as string) ?? ''}
                          onChange={(e) => updateSelected({ slack_channel_id: e.target.value })}
                          placeholder="C0123ABCDEF  (required for Slack approval)"
                          className="builder-input text-[12px]"
                        />
                        <p className="text-[10px] text-white/25 mt-1 leading-snug">
                          Approval card is posted here regardless of how the workflow was triggered.
                          Find the ID in Slack: right-click channel → View channel details.
                        </p>
                      </Field>
                    )}
                  </>
                )
              })()}

              {editable && (
                <>
                  <Field label="Agent">
                    <select
                      value={(selected.data.agentId as string) ?? ''}
                      onChange={(e) => updateSelected({ agentId: e.target.value })}
                      className="builder-input"
                    >
                      <option value="" className="bg-[#1a1a1a]">— select agent —</option>
                      {agents.map((a) => (
                        <option key={a.id} value={a.id} className="bg-[#1a1a1a]">{a.name}</option>
                      ))}
                    </select>
                    {selected.type === 'supervisor' && (
                      <p className="text-[10px] text-amber-400/60 mt-1.5 leading-snug">
                        Outgoing edges become dotted — this agent decides which to follow at runtime.
                      </p>
                    )}
                  </Field>

                  <NodeOverridesPanel
                    data={selected.data as Record<string, unknown>}
                    onChange={updateSelected}
                    isSupervisor={selected.type === 'supervisor'}
                    agent={agents.find((a) => a.id === (selected.data.agentId as string))}
                  />
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {runOpen && (
        <RunModal
          input={runInput}
          setInput={setRunInput}
          onClose={() => setRunOpen(false)}
          onRun={() => { onRun(runInput); setRunOpen(false) }}
        />
      )}

      <style jsx global>{`
        .builder-input {
          width: 100%;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 8px;
          padding: 6px 10px;
          color: white;
          font-size: 13px;
          outline: none;
        }
        .builder-input:focus { border-color: rgba(255,255,255,0.2); }
      `}</style>
    </div>
  )
}

const AVAILABLE_TOOLS = [
  'web_search', 'calculator', 'get_datetime',
  'list_workflows', 'run_workflow', 'get_workflow_status',
  'pause_execution', 'resume_execution', 'terminate_execution',
]

const MODEL_OPTIONS = [
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { value: 'gpt-4o-mini',       label: 'GPT-4o mini' },
  { value: 'gemini-2.5-flash',  label: 'Gemini 2.5 Flash' },
]

function NodeOverridesPanel({
  data,
  onChange,
  isSupervisor,
  agent,
}: {
  data: Record<string, unknown>
  onChange: (patch: Record<string, unknown>) => void
  isSupervisor: boolean
  agent?: Agent
}) {
  // Override value from node data; fall back to agent's configured value
  const strVal = (key: string, agentVal?: string | null) =>
    (data[key] as string | undefined) ?? agentVal ?? ''

  const numStr = (key: string, agentVal?: number) => {
    const v = data[key]
    if (v !== undefined && v !== '') return String(v)
    return agentVal !== undefined ? String(agentVal) : ''
  }

  // Tools: node override takes priority. If no override, show agent's tools as current state.
  const agentTools: string[] = agent?.tools ?? AVAILABLE_TOOLS
  const nodeTools = data.tools
  const effectiveTools: string[] = Array.isArray(nodeTools) ? (nodeTools as string[]) : agentTools
  const hasNodeOverride = Array.isArray(nodeTools)

  const toggleTool = (tool: string) => {
    const next = effectiveTools.includes(tool)
      ? effectiveTools.filter((t) => t !== tool)
      : [...effectiveTools, tool]
    onChange({ tools: next })
  }

  return (
    <div className="border-t border-white/[0.06] pt-3 space-y-3">
      <p className="text-[10px] uppercase tracking-wide text-white/40">Config overrides</p>
      <p className="text-[10px] text-white/25 leading-snug -mt-1">
        Values shown are the agent&apos;s current defaults. Edit any field to override for this node only.
      </p>

      <Field label="System prompt">
        <textarea
          value={strVal('system_prompt', agent?.system_prompt)}
          onChange={(e) => onChange({ system_prompt: e.target.value })}
          rows={3}
          className="builder-input resize-none text-[12px]"
        />
      </Field>

      <Field label="Model">
        <select
          value={strVal('model', agent?.model)}
          onChange={(e) => onChange({ model: e.target.value })}
          className="builder-input text-[12px]"
        >
          {MODEL_OPTIONS.map((m) => (
            <option key={m.value} value={m.value} className="bg-[#1a1a1a]">{m.label}</option>
          ))}
        </select>
      </Field>

      <div className="grid grid-cols-2 gap-2">
        <Field label="Temperature">
          <input
            type="number" min={0} max={1} step={0.05}
            value={numStr('temperature', agent?.temperature)}
            onChange={(e) => onChange({ temperature: e.target.value === '' ? '' : parseFloat(e.target.value) })}
            className="builder-input text-[12px]"
          />
        </Field>
        <Field label="Max tokens">
          <input
            type="number" min={1} step={256}
            value={numStr('max_tokens', agent?.max_tokens)}
            onChange={(e) => onChange({ max_tokens: e.target.value === '' ? '' : parseInt(e.target.value) })}
            className="builder-input text-[12px]"
          />
        </Field>
      </div>

      {!isSupervisor && (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Max iter">
            <input
              type="number" min={1} max={20}
              value={numStr('max_iterations', agent?.max_iterations)}
              onChange={(e) => onChange({ max_iterations: e.target.value === '' ? '' : parseInt(e.target.value) })}
              className="builder-input text-[12px]"
            />
          </Field>
          <Field label="Retries">
            <input
              type="number" min={0} max={5}
              value={numStr('max_retries')}
              onChange={(e) => onChange({ max_retries: e.target.value === '' ? '' : parseInt(e.target.value) })}
              placeholder="1"
              className="builder-input text-[12px]"
            />
          </Field>
        </div>
      )}

      {!isSupervisor && (
        <Field label="Tools">
          <div className="mt-1 space-y-1">
            {AVAILABLE_TOOLS.map((tool) => (
              <label key={tool} className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={effectiveTools.includes(tool)}
                  onChange={() => toggleTool(tool)}
                  className="accent-violet-400"
                />
                <span className="text-[11px] text-white/60 group-hover:text-white/80 font-mono">{tool}</span>
              </label>
            ))}
            {hasNodeOverride && (
              <button
                type="button"
                onClick={() => onChange({ tools: undefined })}
                className="text-[10px] text-white/25 hover:text-white/50 underline mt-1"
              >
                Reset to agent default
              </button>
            )}
          </div>
        </Field>
      )}

      <Field label="Memory (MD)">
        <textarea
          value={strVal('memory_md', agent?.memory_md)}
          onChange={(e) => onChange({ memory_md: e.target.value })}
          rows={2}
          className="builder-input resize-none text-[12px]"
        />
      </Field>

      <Field label="Soul (MD)">
        <textarea
          value={strVal('soul_md', agent?.soul_md)}
          onChange={(e) => onChange({ soul_md: e.target.value })}
          rows={2}
          className="builder-input resize-none text-[12px]"
        />
      </Field>
    </div>
  )
}

function PaletteBtn({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-white/50 hover:text-white bg-white/[0.03] hover:bg-white/[0.08] transition-colors"
    >
      {icon} {label}
    </button>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-white/50 mb-1.5">{label}</label>
      {children}
    </div>
  )
}

function LegendPanel() {
  return (
    <div className="absolute bottom-3 left-3 z-10 bg-[#161616]/90 border border-white/[0.06] rounded-lg px-3 py-2 text-[10px] text-white/50 space-y-1">
      <div className="flex items-center gap-2">
        <span className="w-5 border-t border-white/40" /> deterministic
      </div>
      <div className="flex items-center gap-2">
        <span className="w-5 border-t border-dashed border-amber-400" /> agent-decided
      </div>
    </div>
  )
}

function RunModal({
  input, setInput, onClose, onRun,
}: { input: string; setInput: (v: string) => void; onClose: () => void; onRun: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-[#161616] border border-white/10 rounded-xl p-5 w-[460px]" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-white font-medium text-sm mb-3">Run workflow</h3>
        <textarea
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={4}
          placeholder="Describe the task for the agents…"
          className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-white/20 resize-none"
        />
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg text-sm text-white/40 hover:text-white/70 hover:bg-white/[0.04]">
            Cancel
          </button>
          <button
            onClick={onRun}
            disabled={!input.trim()}
            className="flex-1 py-2 rounded-lg text-sm bg-white text-black font-medium hover:bg-white/90 disabled:opacity-40"
          >
            Run
          </button>
        </div>
      </div>
    </div>
  )
}

function ChannelsPanel({
  config,
  onChange,
  conflict,
}: {
  config: any
  onChange: (c: any) => void
  conflict?: string | null
}) {
  const tg = config.telegram ?? {}
  const sl = config.slack ?? {}

  const setTg = (patch: any) => onChange({ ...config, telegram: { ...tg, ...patch } })
  const setSl = (patch: any) => onChange({ ...config, slack: { ...sl, ...patch } })

  return (
    <div className="space-y-4">
      <p className="text-[10px] uppercase tracking-wide text-white/40 mb-3">Channel Bindings</p>

      {/* Telegram */}
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-sky-500/20 flex items-center justify-center">
              <span className="text-[10px] text-sky-300 font-bold">TG</span>
            </div>
            <span className="text-[13px] font-medium text-white/80">Telegram</span>
          </div>
          <PanelToggle value={tg.enabled ?? false} onChange={(v) => setTg({ enabled: v })} />
        </div>
        {tg.enabled && (
          <div className="space-y-2 pt-1">
            <p className="text-[11px] text-white/30">
              Bind a chat ID in <span className="text-white/50">Workflows List → Telegram channels</span>.
              Inbound messages trigger this workflow; the final output is sent back.
            </p>
            <PanelToggle
              label="Send output back to chat"
              value={tg.send_reply ?? true}
              onChange={(v) => setTg({ send_reply: v })}
            />
          </div>
        )}
      </div>

      {/* Slack */}
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-violet-500/20 flex items-center justify-center">
              <span className="text-[10px] text-violet-300 font-bold">#</span>
            </div>
            <span className="text-[13px] font-medium text-white/80">Slack</span>
          </div>
          <PanelToggle value={sl.enabled ?? false} onChange={(v) => setSl({ enabled: v })} />
        </div>
        {sl.enabled && (
          <div className="space-y-2.5 pt-1">
            <div>
              <label className="text-[11px] text-white/40 mb-1 block">Channel ID</label>
              <input
                value={sl.channel_id ?? ''}
                onChange={(e) => setSl({ channel_id: e.target.value })}
                placeholder="C0123ABCDEF"
                className="builder-input text-[12px]"
              />
              {conflict && (
                <p className="text-[10px] text-amber-400/80 leading-snug bg-amber-500/[0.06] border border-amber-500/15 rounded-md px-2 py-1.5 mt-1.5">
                  ⚠ Channel already used by <span className="font-medium">{conflict}</span>. One channel → one workflow; the most recently saved wins.
                </p>
              )}
            </div>
            <PanelToggle
              label="Socket Mode trigger"
              description="No public URL needed — uses xapp- token"
              value={sl.socket_mode ?? true}
              onChange={(v) => setSl({ socket_mode: v })}
            />
            <PanelToggle
              label="Thread summarizer mode"
              description="When @mentioned, fetch thread context and pass to workflow"
              value={sl.thread_context ?? false}
              onChange={(v) => setSl({ thread_context: v })}
            />
            <PanelToggle
              label="Reply in thread"
              description="Post workflow output back to the Slack thread"
              value={sl.reply_in_thread ?? true}
              onChange={(v) => setSl({ reply_in_thread: v })}
            />
            <div className="rounded-lg bg-emerald-500/[0.04] border border-emerald-500/10 px-2.5 py-2 text-[10px] text-emerald-400/60 leading-relaxed">
              Socket listener starts automatically with the backend. Save this workflow — that's all the setup needed.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function TriggerSource({
  config, onChange, onLabel, onOpenChannels, conflict, workflowId,
}: {
  config: any
  onChange: (c: any) => void
  onLabel: (label: string) => void
  onOpenChannels: () => void
  conflict?: string | null
  workflowId: string
}) {
  const source: 'manual' | 'telegram' | 'slack' | 'schedule' =
    config.schedule?.enabled ? 'schedule'
    : config.slack?.enabled ? 'slack'
    : config.telegram?.enabled ? 'telegram'
    : 'manual'

  const pick = (src: 'manual' | 'telegram' | 'slack' | 'schedule') => {
    onChange({
      ...config,
      telegram:  { ...(config.telegram  ?? {}), enabled: src === 'telegram'  },
      slack:     { ...(config.slack     ?? {}), enabled: src === 'slack'     },
      schedule:  { ...(config.schedule  ?? {}), enabled: src === 'schedule'  },
    })
    const labels: Record<string, string> = {
      slack: 'Slack @mention', telegram: 'Telegram message',
      schedule: 'Scheduled', manual: 'Manual input',
    }
    onLabel(labels[src])
  }

  const SOURCES = ['manual', 'telegram', 'slack', 'schedule'] as const

  return (
    <Field label="Trigger source">
      <div className="grid grid-cols-2 gap-1.5">
        {SOURCES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => pick(s)}
            className={cn(
              'py-1.5 rounded-lg text-[11px] capitalize border transition-colors',
              source === s
                ? 'bg-white/[0.10] text-white border-white/20'
                : 'text-white/40 border-white/[0.06] hover:text-white/70 hover:bg-white/[0.04]'
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {source === 'slack' && (
        <div className="mt-2.5 space-y-1.5">
          <label className="text-[11px] text-white/40">Slack Channel ID</label>
          <input
            value={config.slack?.channel_id ?? ''}
            onChange={(e) => onChange({
              ...config,
              slack: { ...(config.slack ?? {}), enabled: true, channel_id: e.target.value },
            })}
            placeholder="C0123ABCDEF"
            className="builder-input text-[12px]"
          />
          <p className="text-[10px] text-white/25 leading-snug">
            The bot triggers this workflow when @mentioned in this channel. Click <span className="text-white/50">Save</span> to apply.
          </p>
          {conflict && (
            <p className="text-[10px] text-amber-400/80 leading-snug bg-amber-500/[0.06] border border-amber-500/15 rounded-md px-2 py-1.5">
              ⚠ This channel is already used by <span className="font-medium">{conflict}</span>. A channel maps to one workflow — saving this makes it the active one.
            </p>
          )}
        </div>
      )}

      {source === 'telegram' && (
        <p className="text-[10px] text-white/25 mt-2 leading-snug">
          Bind a Telegram chat in the Workflows list. Inbound messages trigger this workflow.
        </p>
      )}

      {source === 'schedule' && (
        <div className="mt-2.5">
          <SchedulesPanel workflowId={workflowId} />
        </div>
      )}

      {source !== 'schedule' && (
        <button
          type="button"
          onClick={onOpenChannels}
          className="text-[10px] text-white/30 hover:text-white/60 mt-2.5 underline underline-offset-2"
        >
          More channel options →
        </button>
      )}
    </Field>
  )
}

function RunsPanel({
  workflowId,
  onOpen,
}: {
  workflowId: string
  onOpen?: (executionId: string) => void
}) {
  const [runs, setRuns] = useState<WorkflowExecution[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await listExecutions(workflowId)
        if (active) setRuns(data)
      } catch {
        /* ignore */
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    // Poll so Slack/Telegram-triggered runs appear without a manual refresh.
    const id = setInterval(load, 4000)
    return () => { active = false; clearInterval(id) }
  }, [workflowId])

  const statusIcon = (s: string) => {
    if (s === 'completed') return <CheckCircle2 size={13} className="text-emerald-400" />
    if (s === 'failed') return <XCircle size={13} className="text-red-400" />
    if (s === 'running' || s === 'pending') return <Loader2 size={13} className="text-amber-300 animate-spin" />
    return <Clock size={13} className="text-white/30" />
  }

  return (
    <div className="space-y-3">
      <p className="text-[10px] uppercase tracking-wide text-white/40">Recent runs</p>
      {loading && runs.length === 0 ? (
        <div className="flex justify-center py-8"><Loader2 size={16} className="animate-spin text-white/20" /></div>
      ) : runs.length === 0 ? (
        <p className="text-white/30 text-xs pt-4">No runs yet. Trigger this workflow from the Run button, Slack, or Telegram.</p>
      ) : (
        <div className="space-y-1.5">
          {runs.map((r) => (
            <button
              key={r.id}
              onClick={() => onOpen?.(r.id)}
              className="w-full flex items-center gap-2.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-left hover:border-white/[0.14] hover:bg-white/[0.04] transition-colors"
            >
              {statusIcon(r.status)}
              <div className="min-w-0 flex-1">
                <p className="text-[12px] text-white/75 capitalize truncate">
                  {r.status}
                  <span className="text-white/30 lowercase"> · {r.trigger_type}</span>
                </p>
                <p className="text-[10px] text-white/30">
                  {new Date(r.created_at).toLocaleString()}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function PanelToggle({
  label, description, value, onChange,
}: { label?: string; description?: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start justify-between gap-2 cursor-pointer">
      {label && (
        <div>
          <span className="text-[12px] text-white/65">{label}</span>
          {description && <p className="text-[10px] text-white/25 mt-0.5">{description}</p>}
        </div>
      )}
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={cn('mt-0.5 w-8 h-[18px] rounded-full p-0.5 transition-colors flex-shrink-0',
          value ? 'bg-emerald-500/70' : 'bg-white/[0.1]')}
      >
        <span className={cn('block w-[14px] h-[14px] rounded-full bg-white transition-transform',
          value && 'translate-x-[14px]')} />
      </button>
    </label>
  )
}

const REPEAT_PRESETS = [
  { label: 'Every 15 min', minutes: 15 },
  { label: 'Every 30 min', minutes: 30 },
  { label: 'Hourly',       minutes: 60 },
  { label: 'Every 6 hrs',  minutes: 360 },
  { label: 'Daily',        minutes: 1440 },
  { label: 'Weekly',       minutes: 10080 },
]

function fmtSchedule(s: WorkflowSchedule): string {
  if (s.schedule_type === 'once') {
    return `Once · ${new Date(s.next_run_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}`
  }
  const preset = REPEAT_PRESETS.find((p) => p.minutes === s.repeat_minutes)
  const interval = preset ? preset.label : `Every ${s.repeat_minutes}m`
  const next = new Date(s.next_run_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
  return `${interval} · next ${next}`
}

function SchedulesPanel({ workflowId }: { workflowId: string }) {
  const [schedules, setSchedules] = useState<WorkflowSchedule[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  // Form state
  const [schedType, setSchedType] = useState<'once' | 'repeat'>('once')
  const [label, setLabel] = useState('')
  const [runAt, setRunAt] = useState('')          // for "once"
  const [repeatMin, setRepeatMin] = useState(60)  // for "repeat"
  const [firstRunAt, setFirstRunAt] = useState('') // first fire for "repeat"
  const [inputText, setInputText] = useState('')

  const load = async () => {
    setLoading(true)
    try { setSchedules(await listSchedules(workflowId)) }
    catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [workflowId])

  const handleCreate = async () => {
    setError(null)
    if (schedType === 'once' && !runAt) { setError('Pick a date/time'); return }
    if (schedType === 'repeat' && !firstRunAt) { setError('Pick the first run time'); return }
    setSaving(true)
    try {
      const nextRunAt = schedType === 'once' ? new Date(runAt).toISOString() : new Date(firstRunAt).toISOString()
      await createSchedule(workflowId, {
        label: label || (schedType === 'once' ? 'One-time run' : 'Repeating run'),
        schedule_type: schedType,
        next_run_at: nextRunAt,
        repeat_minutes: schedType === 'repeat' ? repeatMin : undefined,
        input_text: inputText,
      })
      setShowForm(false)
      setLabel(''); setRunAt(''); setFirstRunAt(''); setInputText('')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create schedule')
    } finally { setSaving(false) }
  }

  const handleDelete = async (s: WorkflowSchedule) => {
    try {
      await deleteSchedule(workflowId, s.id)
      setSchedules((prev) => prev.filter((x) => x.id !== s.id))
    } catch { /* ignore */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-[10px] uppercase tracking-wide text-white/40">Schedules</p>
        <div className="flex items-center gap-1.5">
          <button onClick={load} className="p-1 rounded text-white/30 hover:text-white/60">
            <RefreshCw size={11} />
          </button>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/[0.06] text-white/70 hover:bg-white/[0.10] text-[11px]"
          >
            <Plus size={11} /> New
          </button>
        </div>
      </div>

      {showForm && (
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3.5 space-y-3">
          {/* Type selector */}
          <div className="grid grid-cols-2 gap-1.5">
            {(['once', 'repeat'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setSchedType(t)}
                className={cn(
                  'py-1.5 rounded-lg text-[11px] capitalize border transition-colors',
                  schedType === t ? 'bg-white/[0.10] text-white border-white/20' : 'text-white/40 border-white/[0.06] hover:text-white/70'
                )}
              >
                {t === 'once' ? 'One-time' : 'Repeating'}
              </button>
            ))}
          </div>

          {/* Label */}
          <div>
            <label className="text-[10px] text-white/40 mb-1 block">Label (optional)</label>
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Morning digest"
              className="builder-input text-[12px]" />
          </div>

          {schedType === 'once' ? (
            <div>
              <label className="text-[10px] text-white/40 mb-1 block">Run at</label>
              <input type="datetime-local" value={runAt} onChange={(e) => setRunAt(e.target.value)}
                className="builder-input text-[12px]" />
            </div>
          ) : (
            <>
              <div>
                <label className="text-[10px] text-white/40 mb-1 block">Repeat every</label>
                <select value={repeatMin} onChange={(e) => setRepeatMin(Number(e.target.value))}
                  className="builder-input text-[12px]">
                  {REPEAT_PRESETS.map((p) => (
                    <option key={p.minutes} value={p.minutes} className="bg-[#1a1a1a]">{p.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-white/40 mb-1 block">First run at</label>
                <input type="datetime-local" value={firstRunAt} onChange={(e) => setFirstRunAt(e.target.value)}
                  className="builder-input text-[12px]" />
              </div>
            </>
          )}

          {/* Input */}
          <div>
            <label className="text-[10px] text-white/40 mb-1 block">Workflow input</label>
            <textarea value={inputText} onChange={(e) => setInputText(e.target.value)}
              placeholder="Input passed to the workflow on each run"
              rows={3}
              className="builder-input text-[12px] resize-none" />
          </div>

          {error && <p className="text-[11px] text-red-400">{error}</p>}

          <div className="flex gap-2">
            <button onClick={() => { setShowForm(false); setError(null) }}
              className="flex-1 py-1.5 rounded-lg text-[11px] text-white/40 hover:text-white/70 hover:bg-white/[0.04]">
              Cancel
            </button>
            <button onClick={handleCreate} disabled={saving}
              className="flex-1 py-1.5 rounded-lg text-[11px] bg-white/[0.08] text-white hover:bg-white/[0.12] disabled:opacity-50">
              {saving ? <Loader2 size={11} className="animate-spin inline mr-1" /> : null}
              Create
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center pt-4"><Loader2 size={16} className="animate-spin text-white/30" /></div>
      ) : schedules.length === 0 ? (
        <p className="text-[11px] text-white/25 text-center pt-4">No schedules yet. Click New to add one.</p>
      ) : (
        <div className="space-y-2">
          {schedules.map((s) => (
            <div key={s.id}
              className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <CalendarClock size={11} className={s.is_active ? 'text-emerald-400' : 'text-white/25'} />
                  <span className="text-[12px] font-medium text-white/80 truncate">{s.label}</span>
                  {!s.is_active && (
                    <span className="text-[9px] uppercase tracking-wide text-white/25 bg-white/[0.05] px-1.5 py-0.5 rounded">done</span>
                  )}
                </div>
                <p className="text-[10px] text-white/35 leading-snug">{fmtSchedule(s)}</p>
                {s.input_text && (
                  <p className="text-[10px] text-white/20 mt-1 truncate">Input: {s.input_text}</p>
                )}
                {s.last_run_at && (
                  <p className="text-[9px] text-white/20 mt-0.5">
                    Last ran {new Date(s.last_run_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}
                  </p>
                )}
              </div>
              <button onClick={() => handleDelete(s)}
                className="p-1 rounded text-white/20 hover:text-red-400 flex-shrink-0">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function WorkflowBuilder(props: Props) {
  return (
    <ReactFlowProvider>
      <BuilderInner {...props} />
    </ReactFlowProvider>
  )
}
