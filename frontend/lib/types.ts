export interface Agent {
  id: string
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
  soul_md: string | null
  memory_md: string | null
  guardrails: Record<string, unknown>
  // Flexible display metadata: avatar_emoji, avatar_color, tags, etc.
  meta: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AgentCreate {
  name: string
  description?: string
  role?: string
  system_prompt: string
  model?: string
  provider?: string
  temperature?: number
  max_tokens?: number
  max_iterations?: number
  tools?: string[]
  soul_md?: string | null
  memory_md?: string | null
  guardrails?: Record<string, unknown>
  meta?: Record<string, unknown>
}

export interface AgentUpdate extends Partial<AgentCreate> {}

export interface User {
  id: string
  name: string
  email: string
  created_at: string
}

export interface Session {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Message {
  id?: string
  session_id: string
  role: 'user' | 'assistant' | 'tool'
  content: string   // for role="tool" this is JSON-serialised ToolCall data
  created_at?: string
}

export interface ToolCall {
  id: string          // unique per call
  tool_name: string
  tool_input: Record<string, unknown>
  tool_result?: string
  status: 'running' | 'done'
  started_at: string
  completed_at?: string
}

// ── Workflows ──────────────────────────────────────────────────────────────

export type WorkflowNodeType = 'trigger' | 'agent' | 'supervisor' | 'checkpoint' | 'end'

export interface WorkflowNode {
  id: string
  type: WorkflowNodeType
  position: { x: number; y: number }
  data: {
    label: string
    description?: string
    agentId?: string
    [k: string]: unknown
  }
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  [k: string]: unknown
}

export interface GraphJson {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  channel_config?: Record<string, any>
}

export interface Workflow {
  id: string
  user_id: string
  name: string
  description: string
  graph_json: GraphJson
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface WorkflowCreate {
  name: string
  description?: string
  graph_json: GraphJson
}

export interface WorkflowTemplate {
  key: string
  name: string
  description: string
  agent_count: number
  preview_graph: GraphJson
}

export type ExecutionStatus =
  | 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused'

export interface WorkflowExecution {
  id: string
  workflow_id: string
  user_id: string
  status: ExecutionStatus
  trigger_type: string
  trigger_context: Record<string, unknown>
  input_data: Record<string, unknown>
  output_data: { output?: string; node_outputs?: Record<string, string> } | null
  error_message: string | null
  celery_task_id: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface WorkflowStep {
  id: string
  execution_id: string
  node_id: string
  agent_id: string | null
  status: string
  input: Record<string, unknown>
  output: { text?: string; decision?: Record<string, unknown>; usage?: Record<string, number> } | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

// Live SSE event shapes published by the worker during a run.
export type ExecutionEvent =
  | { type: 'stream_open' }
  | { type: 'execution_started'; execution_id: string; workflow_id: string; name: string; ts: string }
  | { type: 'node_started'; execution_id: string; node_id: string; label: string; role: string; ts: string }
  | { type: 'chunk'; execution_id: string; node_id: string; content: string; ts: string }
  | { type: 'tool_start'; execution_id: string; node_id: string; tool_name: string; tool_input: unknown; ts: string }
  | { type: 'tool_end'; execution_id: string; node_id: string; tool_name: string; tool_result: string; ts: string }
  | { type: 'supervisor_decision'; execution_id: string; node_id: string; next: string; reason: string; ts: string }
  | { type: 'node_completed'; execution_id: string; node_id: string; output: string; usage?: Record<string, number>; ts: string }
  | { type: 'node_failed'; execution_id: string; node_id: string; error: string; ts: string }
  | { type: 'approval_requested'; execution_id: string; node_id: string; preview: string; ts: string }
  | { type: 'tool_approval_requested'; execution_id: string; node_id: string; tool_name: string; tool_input: Record<string, unknown>; call_id: string; ts: string }
  | { type: 'output_sent'; execution_id: string; platform: string; chat_id: string; ts: string }
  | { type: 'execution_completed'; execution_id: string; output: string; ts: string }
  | { type: 'execution_failed'; execution_id: string; error: string; ts: string }
  | { type: 'execution_paused'; execution_id: string; ts: string }

export interface ExecutionWithWorkflow extends WorkflowExecution {
  workflow_name: string
}

export interface SpanEvent {
  id: string
  event_type: 'tool_start' | 'tool_end' | 'supervisor_decision' | string
  payload: Record<string, unknown>
  created_at: string
}

export interface TraceSpan {
  id: string
  node_id: string
  node_label: string
  span_type: 'agent' | 'supervisor' | 'checkpoint' | 'trigger' | 'end' | string
  agent_name: string | null
  model: string | null
  provider: string | null
  max_tokens: number | null
  status: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  input: Record<string, unknown>
  output: { text?: string; decision?: Record<string, unknown>; usage?: Record<string, number> } | null
  error_message: string | null
  events: SpanEvent[]
}

export interface ExecutionTrace {
  execution_id: string
  workflow_id: string
  workflow_name: string
  status: string
  trigger_type: string
  input_text: string
  output_text: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  total_input_tokens: number
  total_output_tokens: number
  total_cost_usd: number
  spans: TraceSpan[]
}

export interface WorkflowSchedule {
  id: string
  workflow_id: string
  user_id: string
  label: string
  schedule_type: 'once' | 'repeat'
  repeat_minutes: number | null
  input_text: string
  is_active: boolean
  next_run_at: string
  last_run_at: string | null
  created_at: string
}

export interface WorkflowScheduleCreate {
  label?: string
  schedule_type: 'once' | 'repeat'
  next_run_at: string   // ISO datetime
  repeat_minutes?: number
  input_text?: string
}

export interface ChannelBinding {
  id: string
  user_id: string
  platform: string
  external_id: string
  workflow_id: string | null
  agent_id: string | null
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
}

export type WSMessageType =
  | { type: 'session_info'; session_id: string; title: string }
  | { type: 'session_title'; session_id: string; title: string }
  | { type: 'chunk'; content: string }
  | { type: 'done'; session_id: string }
  | { type: 'stopped'; session_id: string }
  | { type: 'provider_fallback'; from: string; to: string; reason: string }
  | { type: 'error'; error: string }
  | { type: 'tool_start'; tool_name: string; tool_input: Record<string, unknown> }
  | { type: 'tool_end'; tool_name: string; tool_result: string }
