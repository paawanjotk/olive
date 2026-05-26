'use client'

import { useState } from 'react'
import { useChat } from '@/hooks/useChat'
import ChatSidebar from './ChatSidebar'
import ChatMain from './ChatMain'
import AgentsPanel from '@/components/agents/AgentsPanel'

type AppView = 'chat' | 'agents'

export default function ChatInterface() {
  const chat = useChat()
  const [activeView, setActiveView] = useState<AppView>('chat')

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
