import type {
  User, Session, Message, Agent, AgentCreate, AgentUpdate,
  Workflow, WorkflowCreate, WorkflowTemplate, WorkflowExecution, WorkflowStep,
  GraphJson, ChannelBinding, ExecutionWithWorkflow, ExecutionTrace,
} from './types'
import { supabase } from './supabase'

const HTTP_BASE =
  process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || 'http://localhost:8000'
const API_BASE = `${HTTP_BASE}/api/v1`

export { API_BASE }

export async function getAccessToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}


async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders()
  const url = `${API_BASE}${path}`
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`
    try {
      const errorBody = await response.json()
      if (errorBody.detail) {
        errorMessage =
          typeof errorBody.detail === 'string'
            ? errorBody.detail
            : JSON.stringify(errorBody.detail)
      }
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(errorMessage)
  }

  // 204 No Content has no body
  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

// ---- Auth ----

export async function syncUser(accessToken: string): Promise<User> {
  const url = `${API_BASE}/auth/sync`
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
  })
  if (!response.ok) throw new Error(`Sync failed: ${response.status}`)
  return response.json()
}

// ---- User endpoints ----

export async function createOrGetUser(
  name: string,
  email: string
): Promise<User> {
  return apiRequest<User>('/users', {
    method: 'POST',
    body: JSON.stringify({ name, email }),
  })
}

export async function getUserById(userId: string): Promise<User> {
  return apiRequest<User>(`/users/${userId}`)
}

// ---- Session endpoints ----

export async function getSessions(userId: string): Promise<Session[]> {
  const data = await apiRequest<{ sessions: Session[] }>(
    `/sessions/user/${userId}`
  )
  return data.sessions
}

export async function createSession(
  userId: string,
  title?: string
): Promise<Session> {
  return apiRequest<Session>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, title: title || 'New Chat' }),
  })
}

export async function updateSessionTitle(
  sessionId: string,
  title: string,
  userId: string
): Promise<Session> {
  return apiRequest<Session>(`/sessions/${sessionId}?user_id=${userId}`, {
    method: 'PUT',
    body: JSON.stringify({ title }),
  })
}

export async function deleteSession(sessionId: string, userId: string): Promise<void> {
  return apiRequest<void>(`/sessions/${sessionId}?user_id=${userId}`, {
    method: 'DELETE',
  })
}

export async function getSessionMessages(sessionId: string, userId: string): Promise<Message[]> {
  const data = await apiRequest<{ messages: Message[]; session: Session }>(
    `/sessions/${sessionId}/messages?user_id=${userId}`
  )
  return data.messages
}

// ---- Agent endpoints ----

export async function listAgents(): Promise<Agent[]> {
  return apiRequest<Agent[]>('/agents')
}

export async function getAgent(agentId: string): Promise<Agent> {
  return apiRequest<Agent>(`/agents/${agentId}`)
}

export async function createAgent(data: AgentCreate): Promise<Agent> {
  return apiRequest<Agent>('/agents', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAgent(agentId: string, data: AgentUpdate): Promise<Agent> {
  return apiRequest<Agent>(`/agents/${agentId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteAgent(agentId: string): Promise<void> {
  return apiRequest<void>(`/agents/${agentId}`, { method: 'DELETE' })
}

export async function testAgent(
  agentId: string,
  message: string
): Promise<{ response: string; provider_used: string }> {
  return apiRequest(`/agents/${agentId}/test`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

// ---- Workflow endpoints ----

export async function listWorkflows(): Promise<Workflow[]> {
  return apiRequest<Workflow[]>('/workflows')
}

export async function getWorkflow(id: string): Promise<Workflow> {
  return apiRequest<Workflow>(`/workflows/${id}`)
}

export async function createWorkflow(data: WorkflowCreate): Promise<Workflow> {
  return apiRequest<Workflow>('/workflows', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateWorkflow(
  id: string,
  data: Partial<WorkflowCreate>
): Promise<Workflow> {
  return apiRequest<Workflow>(`/workflows/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteWorkflow(id: string): Promise<void> {
  return apiRequest<void>(`/workflows/${id}`, { method: 'DELETE' })
}

export async function listTemplates(): Promise<WorkflowTemplate[]> {
  return apiRequest<WorkflowTemplate[]>('/workflows/templates')
}

export async function cloneTemplate(key: string): Promise<Workflow> {
  return apiRequest<Workflow>(`/workflows/templates/${key}/clone`, { method: 'POST' })
}

export async function executeWorkflow(
  id: string,
  input: string,
  triggerType = 'manual'
): Promise<WorkflowExecution> {
  return apiRequest<WorkflowExecution>(`/workflows/${id}/execute`, {
    method: 'POST',
    body: JSON.stringify({ input, trigger_type: triggerType }),
  })
}

export async function listExecutions(workflowId: string): Promise<WorkflowExecution[]> {
  return apiRequest<WorkflowExecution[]>(`/workflows/${workflowId}/executions`)
}

export async function getExecution(executionId: string): Promise<WorkflowExecution> {
  return apiRequest<WorkflowExecution>(`/workflows/executions/${executionId}`)
}

export async function getExecutionSteps(executionId: string): Promise<WorkflowStep[]> {
  return apiRequest<WorkflowStep[]>(`/workflows/executions/${executionId}/steps`)
}

export async function listAllExecutions(skip = 0, limit = 50): Promise<ExecutionWithWorkflow[]> {
  return apiRequest<ExecutionWithWorkflow[]>(`/workflows/executions?skip=${skip}&limit=${limit}`)
}

export async function cancelExecution(executionId: string): Promise<void> {
  return apiRequest<void>(`/workflows/executions/${executionId}/cancel`, { method: 'POST' })
}

export async function pauseExecution(executionId: string): Promise<void> {
  return apiRequest<void>(`/workflows/executions/${executionId}/pause`, { method: 'POST' })
}

export async function resumeExecution(executionId: string): Promise<void> {
  return apiRequest<void>(`/workflows/executions/${executionId}/resume`, { method: 'POST' })
}

export async function terminateExecution(executionId: string): Promise<void> {
  return apiRequest<void>(`/workflows/executions/${executionId}/terminate`, { method: 'POST' })
}

export async function approveCheckpoint(
  executionId: string,
  nodeId: string,
  approved: boolean,
  reason = ''
): Promise<void> {
  return apiRequest<void>(`/workflows/executions/${executionId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ node_id: nodeId, approved, reason }),
  })
}

export async function approveToolCall(
  executionId: string,
  callId: string,
  approved: boolean,
  reason = ''
): Promise<void> {
  return apiRequest<void>(`/workflows/executions/${executionId}/approve_tool`, {
    method: 'POST',
    body: JSON.stringify({ call_id: callId, approved, reason }),
  })
}

export async function getExecutionTrace(executionId: string): Promise<ExecutionTrace> {
  return apiRequest<ExecutionTrace>(`/workflows/executions/${executionId}/trace`)
}

/** Build the SSE URL for a live execution stream (token passed as query param). */
export async function executionStreamUrl(executionId: string): Promise<string> {
  const token = await getAccessToken()
  return `${API_BASE}/workflows/executions/${executionId}/stream?token=${encodeURIComponent(token ?? '')}`
}

// ---- Channel endpoints ----

export async function listChannelBindings(): Promise<ChannelBinding[]> {
  return apiRequest<ChannelBinding[]>('/channels')
}

export async function createChannelBinding(data: {
  platform: string
  external_id: string
  workflow_id?: string
  agent_id?: string
}): Promise<ChannelBinding> {
  return apiRequest<ChannelBinding>('/channels', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteChannelBinding(id: string): Promise<void> {
  return apiRequest<void>(`/channels/${id}`, { method: 'DELETE' })
}

// ── Unified channel connect / status / disconnect ─────────────────────────────
// Adding a new channel on the frontend = add typed wrappers below. No API changes.

type SlackConnectResult  = { connected: true; workspace_name: string; team_id: string }
type TelegramConnectResult = { pending: true; code: string; bot_username: string; instruction: string; expires_in_seconds: number }

export async function channelConnect(platform: 'slack'): Promise<SlackConnectResult>
export async function channelConnect(platform: 'telegram'): Promise<TelegramConnectResult>
export async function channelConnect(platform: string, config: Record<string, unknown> = {}): Promise<unknown> {
  return apiRequest('/channels/connect', {
    method: 'POST',
    body: JSON.stringify({ platform, config }),
  })
}

export async function channelStatus(platform: string): Promise<{ connected: boolean; [k: string]: unknown }> {
  return apiRequest(`/channels/status?platform=${encodeURIComponent(platform)}`)
}

export async function channelDisconnect(platform: string): Promise<void> {
  return apiRequest(`/channels/disconnect?platform=${encodeURIComponent(platform)}`, { method: 'DELETE' })
}

// Typed convenience wrappers kept for backwards compat with SettingsPanel
export const slackConnect    = () => channelConnect('slack')
export const slackStatus     = () => channelStatus('slack') as Promise<{ connected: boolean; workspace_name?: string; team_id?: string }>
export const slackDisconnect = () => channelDisconnect('slack')

export const telegramGenerateCode = () => channelConnect('telegram') as Promise<TelegramConnectResult>
export const telegramStatus       = () => channelStatus('telegram') as Promise<{ connected: boolean; chat_id?: string }>
export const telegramDisconnect   = () => channelDisconnect('telegram')
