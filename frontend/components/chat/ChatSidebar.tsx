'use client'

import { useState, useRef, useEffect } from 'react'
import {
  SquarePen,
  Bot,
  Workflow,
  Activity,
  Settings,
  PanelLeft,
  Trash2,
  Check,
  X,
  Pencil,
  LogOut,
} from 'lucide-react'
import { cn, truncate } from '@/lib/utils'
import type { Session, User } from '@/lib/types'

type AppView = 'chat' | 'agents' | 'workflows' | 'monitoring' | 'settings'

interface ChatSidebarProps {
  user: User | null
  sessions: Session[]
  activeSessionId: string | null
  isLoadingSessions: boolean
  activeView: 'chat' | 'agents' | 'workflows' | 'monitoring' | 'settings'
  selectSession: (id: string) => void
  startNewChat: () => void
  deleteSession: (id: string) => void
  renameSession: (id: string, title: string) => void
  onViewChange: (view: 'chat' | 'agents' | 'workflows' | 'monitoring' | 'settings') => void
  onSignOut: () => void
}

function SessionSkeleton() {
  return (
    <div className="space-y-1 px-2">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg">
          <div
            className="skeleton h-3 rounded flex-grow"
            style={{ width: `${55 + i * 9}%`, opacity: 1 - i * 0.12 }}
          />
        </div>
      ))}
    </div>
  )
}

interface SessionItemProps {
  session: Session
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
  onRename: (title: string) => void
}

function SessionItem({ session, isActive, onSelect, onDelete, onRename }: SessionItemProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(session.title)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditTitle(session.title)
    setIsEditing(true)
  }

  const handleConfirmEdit = () => {
    const trimmed = editTitle.trim()
    if (trimmed && trimmed !== session.title) onRename(trimmed)
    setIsEditing(false)
  }

  const handleCancelEdit = () => {
    setEditTitle(session.title)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleConfirmEdit()
    if (e.key === 'Escape') handleCancelEdit()
  }

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete()
  }

  return (
    <div
      className={cn(
        'group relative flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer',
        'transition-colors duration-100 select-none',
        isActive
          ? 'bg-white/[0.08] text-white'
          : 'text-[#b4b4b4] hover:bg-white/[0.05] hover:text-white'
      )}
      onClick={!isEditing ? onSelect : undefined}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isEditing ? (
        <input
          ref={inputRef}
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleCancelEdit}
          className="flex-1 bg-transparent text-sm text-white outline-none border-b border-white/20 min-w-0 py-0.5"
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <span className="flex-1 text-sm truncate min-w-0">{truncate(session.title, 30)}</span>
      )}

      {isEditing ? (
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onMouseDown={(e) => { e.preventDefault(); handleConfirmEdit() }}
            className="p-0.5 rounded text-white/50 hover:text-white transition-colors"
          >
            <Check size={12} />
          </button>
          <button
            onMouseDown={(e) => { e.preventDefault(); handleCancelEdit() }}
            className="p-0.5 rounded text-white/30 hover:text-white/60 transition-colors"
          >
            <X size={12} />
          </button>
        </div>
      ) : (
        (isHovered || isActive) && (
          <div className="flex items-center gap-0.5 flex-shrink-0">
            <button
              onClick={handleStartEdit}
              className="p-1 rounded text-white/30 hover:text-white/70 hover:bg-white/[0.08] transition-colors"
              title="Rename"
            >
              <Pencil size={11} />
            </button>
            <button
              onClick={handleDelete}
              className="p-1 rounded text-white/30 hover:text-red-400 hover:bg-white/[0.08] transition-colors"
              title="Delete"
            >
              <Trash2 size={11} />
            </button>
          </div>
        )
      )}
    </div>
  )
}

const NAV_ITEMS = [
  { icon: Bot,      label: 'Agents',     view: 'agents'     as const },
  { icon: Workflow, label: 'Workflows',  view: 'workflows'  as const },
  { icon: Activity, label: 'Monitoring', view: 'monitoring' as const },
  { icon: Settings, label: 'Settings',   view: 'settings'   as const },
]

export default function ChatSidebar({
  user,
  sessions,
  activeSessionId,
  isLoadingSessions,
  activeView,
  selectSession,
  startNewChat,
  deleteSession,
  renameSession,
  onViewChange,
  onSignOut,
}: ChatSidebarProps) {
  const initials = user?.name
    ? user.name
        .split(' ')
        .slice(0, 2)
        .map((n) => n[0])
        .join('')
        .toUpperCase()
    : user?.email
    ? user.email[0].toUpperCase()
    : 'U'

  const displayName = user?.name || user?.email?.split('@')[0] || 'User'

  return (
    <aside className="w-64 flex-shrink-0 bg-[#111111] flex flex-col h-full">
      {/* Top bar: logo + collapse icon */}
      <div className="flex items-center justify-between px-3 pt-2.5 pb-1.5">
        <div className="flex items-center gap-2 px-1.5 py-1">
          <div className="w-7 h-7 rounded-lg bg-white/[0.08] flex items-center justify-center flex-shrink-0">
            <span className="text-white text-xs font-bold">O</span>
          </div>
        </div>
        <button className="p-2 rounded-lg hover:bg-white/[0.06] text-white/25 hover:text-white/60 transition-colors">
          <PanelLeft size={15} />
        </button>
      </div>

      {/* New chat */}
      <div className="px-2 pb-1">
        <button
          onClick={startNewChat}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-[#c0c0c0] hover:bg-white/[0.06] hover:text-white transition-colors text-sm"
        >
          <SquarePen size={15} className="flex-shrink-0 text-white/60" />
          <span>New chat</span>
        </button>
      </div>

      {/* Nav items */}
      <nav className="px-2 space-y-0.5 pb-1">
        {NAV_ITEMS.map(({ icon: Icon, label, view }) => {
          const isActive = view !== null && activeView === view
          return (
            <button
              key={label}
              onClick={() => view && onViewChange(isActive ? 'chat' : view)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm',
                isActive
                  ? 'bg-white/[0.08] text-white'
                  : 'text-[#c0c0c0] hover:bg-white/[0.06] hover:text-white'
              )}
            >
              <Icon size={15} className={cn('flex-shrink-0', isActive ? 'text-white/80' : 'text-white/60')} />
              <span>{label}</span>
            </button>
          )
        })}
      </nav>

      {/* Recents section */}
      <div className="flex-1 overflow-y-auto min-h-0 mt-3">
        <div className="px-4 mb-1.5">
          <span className="text-[#686868] text-xs font-medium">Recents</span>
        </div>

        {isLoadingSessions ? (
          <SessionSkeleton />
        ) : sessions.length === 0 ? (
          <div className="px-4 py-5">
            <p className="text-[#505050] text-sm">No conversations yet</p>
          </div>
        ) : (
          <div className="px-2 space-y-0.5">
            {sessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isActive={activeSessionId === session.id}
                onSelect={() => selectSession(session.id)}
                onDelete={() => deleteSession(session.id)}
                onRename={(title) => renameSession(session.id, title)}
              />
            ))}
          </div>
        )}
      </div>

      {/* User footer */}
      <div className="px-2 py-2.5 border-t border-white/[0.06]">
        <div className="flex items-center gap-1">
          <div className="flex-1 flex items-center gap-3 px-3 py-2 rounded-lg min-w-0">
            <div className="w-8 h-8 rounded-full bg-[#10a37f] flex items-center justify-center text-white text-xs font-bold flex-shrink-0 select-none">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate leading-tight">
                {displayName}
              </p>
              {user?.email && (
                <p className="text-[#686868] text-xs truncate leading-tight mt-0.5">
                  {user.email}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={onSignOut}
            title="Sign out"
            className="p-2 rounded-lg text-white/25 hover:text-white/60 hover:bg-white/[0.06] transition-colors flex-shrink-0"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  )
}
