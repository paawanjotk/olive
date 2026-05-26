'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useChat } from '@/hooks/useChat'
import { useAuth } from '@/contexts/AuthContext'
import ChatSidebar from './ChatSidebar'
import ChatMain from './ChatMain'
import AgentsPanel from '@/components/agents/AgentsPanel'

type AppView = 'chat' | 'agents'

export default function ChatInterface() {
  const { session, loading, signOut } = useAuth()
  const router = useRouter()
  const chat = useChat()
  const [activeView, setActiveView] = useState<AppView>('chat')

  useEffect(() => {
    if (!loading && !session) router.replace('/login')
  }, [session, loading, router])

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

      {activeView === 'agents' ? (
        <AgentsPanel />
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
