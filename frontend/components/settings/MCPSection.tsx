'use client'

import { useState, useEffect, useCallback } from 'react'
import { Github, BookOpen, Check, X, ExternalLink, Loader2 } from 'lucide-react'
import { getMCPConnections, mcpOAuthStart, disconnectMCP } from '@/lib/api'
import type { MCPConnection } from '@/lib/types'

// ── Provider card ─────────────────────────────────────────────────────────────

interface ProviderConfig {
  id: 'github' | 'notion'
  label: string
  description: string
  icon: React.ReactNode
  accent: string
  docsHint: string
}

const PROVIDERS: ProviderConfig[] = [
  {
    id: 'github',
    label: 'GitHub',
    description: 'List repos, browse files, manage issues and PRs, search code',
    icon: <Github className="w-5 h-5" />,
    accent: '#24292e',
    docsHint: 'Create a GitHub OAuth App at github.com/settings/developers',
  },
  {
    id: 'notion',
    label: 'Notion',
    description: 'Search pages, read and create content, query databases',
    icon: <BookOpen className="w-5 h-5" />,
    accent: '#191919',
    docsHint: 'Create a Notion OAuth integration at notion.so/my-integrations',
  },
]

function ProviderCard({
  config,
  connection,
  onConnect,
  onDisconnect,
}: {
  config: ProviderConfig
  connection: MCPConnection | undefined
  onConnect: (id: string) => void
  onDisconnect: (id: string) => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const connected = connection?.connected ?? false

  async function handleConnect() {
    setLoading(true); setError('')
    try {
      await onConnect(config.id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to connect')
    } finally { setLoading(false) }
  }

  async function handleDisconnect() {
    setLoading(true); setError('')
    try {
      await onDisconnect(config.id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to disconnect')
    } finally { setLoading(false) }
  }

  const displayName = config.id === 'github'
    ? (connection?.meta?.login as string | undefined)
    : (connection?.meta?.workspace_name as string | undefined)

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-center gap-3 mb-4">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center text-white flex-shrink-0"
          style={{ backgroundColor: config.accent }}
        >
          {config.icon}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white">{config.label}</h3>
          <p className="text-xs text-white/50 truncate">{config.description}</p>
        </div>
        {connected && (
          <span className="flex-shrink-0 flex items-center gap-1.5 text-xs text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Connected
          </span>
        )}
      </div>

      {connected ? (
        <div className="space-y-3">
          {displayName && (
            <div className="rounded-lg bg-white/5 px-4 py-2.5 text-sm text-white/70 flex items-center gap-2">
              <Check size={13} className="text-emerald-400 flex-shrink-0" />
              {config.id === 'github' ? 'Account' : 'Workspace'}:{' '}
              <span className="text-white font-medium">{displayName}</span>
            </div>
          )}

          {/* Available tools summary */}
          <div className="rounded-lg bg-white/[0.03] border border-white/[0.06] px-3 py-2">
            <p className="text-[11px] text-white/40 mb-1.5 font-medium uppercase tracking-wider">Available tools</p>
            <div className="flex flex-wrap gap-1">
              {getToolNames(config.id).map((t) => (
                <span key={t} className="text-[10px] bg-white/[0.06] text-white/50 px-2 py-0.5 rounded-full font-mono">
                  {t}
                </span>
              ))}
            </div>
          </div>

          <button
            onClick={handleDisconnect}
            disabled={loading}
            className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50 transition-colors flex items-center gap-1"
          >
            {loading ? <Loader2 size={11} className="animate-spin" /> : <X size={11} />}
            Disconnect {config.label}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-white/40 leading-relaxed">
            {config.docsHint}. Set{' '}
            <code className="bg-white/10 px-1 rounded">{config.id.toUpperCase()}_CLIENT_ID</code> and{' '}
            <code className="bg-white/10 px-1 rounded">{config.id.toUpperCase()}_CLIENT_SECRET</code>{' '}
            in <code className="bg-white/10 px-1 rounded">backend/.env</code>, then connect.
          </p>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            onClick={handleConnect}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg text-white text-sm font-medium px-4 py-2 transition-colors disabled:opacity-50"
            style={{ backgroundColor: config.accent }}
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <ExternalLink size={14} />}
            {loading ? 'Connecting…' : `Connect ${config.label}`}
          </button>
        </div>
      )}
    </div>
  )
}

function getToolNames(provider: 'github' | 'notion'): string[] {
  if (provider === 'github') {
    return ['list_repos', 'get_repo', 'list_issues', 'create_issue', 'list_prs', 'get_file', 'search_code']
  }
  return ['search', 'get_page', 'get_page_content', 'create_page', 'append_block', 'query_database']
}

// ── Main MCP section ──────────────────────────────────────────────────────────

export default function MCPSection() {
  const [connections, setConnections] = useState<MCPConnection[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const conns = await getMCPConnections()
      setConnections(conns)
    } catch {
      // Silently fail — backend may not have MCP configured yet
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Listen for OAuth popup result
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      if (event.origin !== window.location.origin) return
      if (event.data?.type === 'mcp_oauth_result') {
        load() // refresh connection list
      }
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [load])

  async function handleConnect(provider: string) {
    const { url } = await mcpOAuthStart(provider)
    const popup = window.open(url, `mcp_oauth_${provider}`, 'width=600,height=700,scrollbars=yes')
    if (!popup) {
      // Popup blocked — fall back to same-tab redirect
      window.location.href = url
    }
  }

  async function handleDisconnect(provider: string) {
    await disconnectMCP(provider)
    await load()
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <div key={i} className="rounded-xl border border-white/10 bg-white/5 p-5 animate-pulse h-28" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {PROVIDERS.map((cfg) => (
        <ProviderCard
          key={cfg.id}
          config={cfg}
          connection={connections.find((c) => c.provider === cfg.id)}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
        />
      ))}
    </div>
  )
}
