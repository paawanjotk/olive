import { create } from 'zustand'
import type { User, Session, Message, ToolCall } from '@/lib/types'


interface ChatStore {
  // User state
  user: User | null
  setUser: (user: User | null) => void

  // Sessions
  sessions: Session[]
  activeSessionId: string | null
  setSessions: (sessions: Session[]) => void
  setActiveSession: (id: string | null) => void
  addSession: (session: Session) => void
  updateSessionTitle: (id: string, title: string) => void
  removeSession: (id: string) => void

  // Messages (for the current active session)
  messages: Message[]
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void

  // Chat UI state
  isStreaming: boolean
  setIsStreaming: (v: boolean) => void
  streamingContent: string
  setStreamingContent: (v: string) => void
  appendStreamingContent: (v: string) => void
  clearStreamingContent: () => void

  // Tool calls (active during a streaming agent turn)
  toolCalls: ToolCall[]
  addToolCall: (call: ToolCall) => void
  completeToolCall: (tool_name: string, result: string) => void
  clearToolCalls: () => void

  // Ephemeral provider-fallback notice (not persisted)
  providerFallback: { from: string; to: string; reason: string } | null
  setProviderFallback: (v: { from: string; to: string; reason: string } | null) => void

  // Loading states
  isLoadingSessions: boolean
  setIsLoadingSessions: (v: boolean) => void
  isLoadingMessages: boolean
  setIsLoadingMessages: (v: boolean) => void
}

export const useChatStore = create<ChatStore>((set) => ({
  // User state
  user: null,
  setUser: (user) => set({ user }),

  // Sessions
  sessions: [],
  activeSessionId: null,
  setSessions: (sessions) => set({ sessions }),
  setActiveSession: (id) => set({ activeSessionId: id }),
  addSession: (session) =>
    set((state) => ({
      sessions: [session, ...state.sessions.filter((s) => s.id !== session.id)],
    })),
  updateSessionTitle: (id, title) =>
    set((state) => ({
      sessions: state.sessions.map((s) => (s.id === id ? { ...s, title } : s)),
    })),
  removeSession: (id) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
      activeSessionId: state.activeSessionId === id ? null : state.activeSessionId,
      messages: state.activeSessionId === id ? [] : state.messages,
    })),

  // Messages
  messages: [],
  setMessages: (messages) => set({ messages }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  // Streaming state
  isStreaming: false,
  setIsStreaming: (v) => set({ isStreaming: v }),
  streamingContent: '',
  setStreamingContent: (v) => set({ streamingContent: v }),
  appendStreamingContent: (v) =>
    set((state) => ({ streamingContent: state.streamingContent + v })),
  clearStreamingContent: () => set({ streamingContent: '' }),

  // Tool calls
  toolCalls: [],
  addToolCall: (call) =>
    set((state) => ({ toolCalls: [...state.toolCalls, call] })),
  completeToolCall: (tool_name, result) =>
    set((state) => ({
      toolCalls: state.toolCalls.map((c) =>
        c.tool_name === tool_name && c.status === 'running'
          ? { ...c, status: 'done', tool_result: result, completed_at: new Date().toISOString() }
          : c
      ),
    })),
  clearToolCalls: () => set({ toolCalls: [] }),

  // Ephemeral provider-fallback notice
  providerFallback: null,
  setProviderFallback: (v) => set({ providerFallback: v }),

  // Loading states
  isLoadingSessions: false,
  setIsLoadingSessions: (v) => set({ isLoadingSessions: v }),
  isLoadingMessages: false,
  setIsLoadingMessages: (v) => set({ isLoadingMessages: v }),
}))
