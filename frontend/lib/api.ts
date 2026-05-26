import type { User, Session, Message, Agent, AgentCreate, AgentUpdate } from './types'
import { supabase } from './supabase'

const HTTP_BASE =
  process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || 'http://localhost:8000'
const API_BASE = `${HTTP_BASE}/api/v1`


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
