'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useChat } from '@/hooks/useChat'
import { useAuth } from '@/contexts/AuthContext'
import ChatSidebar from './ChatSidebar'
import ChatMain from './ChatMain'
import AgentsPanel from '@/components/agents/AgentsPanel'
import WorkflowsPanel from '@/components/workflows/WorkflowsPanel'
import MonitoringPanel from '@/components/monitoring/MonitoringPanel'
import SettingsPanel from '@/components/settings/SettingsPanel'

type AppView = 'chat' | 'agents' | 'workflows' | 'monitoring' | 'settings'

export default function ChatInterface() {
  const { session, loading, signOut } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const chat = useChat()
  const [activeView, setActiveView] = useState<AppView>('chat')

  useEffect(() => {
    if (!loading && !session) router.replace('/login')
  }, [session, loading, router])

  // After popup-blocked OAuth same-tab flow, land back here with ?mcp_connected=
  useEffect(() => {
    if (searchParams.get('mcp_connected') || searchParams.get('mcp_error')) {
      setActiveView('settings')
      // Clean up the query param without a full reload
      router.replace('/', { scroll: false })
    }
  }, [searchParams, router])

  if (loading || !session) return null

  return (
    <div className="flex h-screen bg-[#0d0d0d] overflow-hidden">
      <ChatSidebar
        user={chat.user}
        sessions={chat.sessions}
        activeSessionId={chat.activeSessionId}
        isLoadingSessions={chat.isLoadingSessions}
        activeView={activeView}
        selectSession={(id) => { chat.selectSession(id); setActiveView('chat') }}
        startNewChat={() => { chat.startNewChat(); setActiveView('chat') }}
        deleteSession={chat.deleteSession}
        renameSession={chat.renameSession}
        onViewChange={setActiveView}
        onSignOut={signOut}
      />

      {activeView === 'settings' ? (
        <SettingsPanel />
      ) : activeView === 'monitoring' ? (
        <MonitoringPanel />
      ) : activeView === 'agents' ? (
        <AgentsPanel />
      ) : activeView === 'workflows' ? (
        <WorkflowsPanel />
      ) : (
        <ChatMain
          sessions={chat.sessions}
          activeSessionId={chat.activeSessionId}
          messages={chat.messages}
          isStreaming={chat.isStreaming}
          streamingContent={chat.streamingContent}
          toolCalls={chat.toolCalls}
          isLoadingMessages={chat.isLoadingMessages}
          isConnected={chat.isConnected}
          selectedAgentId={chat.selectedAgentId}
          onSelectAgent={chat.setSelectedAgentId}
          sendChatMessage={chat.sendChatMessage}
          stopGeneration={chat.stopGeneration}
          messagesEndRef={chat.messagesEndRef}
        />
      )}
    </div>
  )
}
