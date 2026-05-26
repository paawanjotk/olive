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
