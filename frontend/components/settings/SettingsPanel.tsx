'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  slackConnect, slackStatus, slackDisconnect,
  telegramGenerateCode, telegramStatus, telegramDisconnect,
} from '@/lib/api'
import MCPSection from './MCPSection'

// ── Slack section ─────────────────────────────────────────────────────────────

function SlackSection() {
  const [status, setStatus] = useState<{ connected: boolean; workspace_name?: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try { setStatus(await slackStatus()) } catch { /* token not configured */ }
  }, [])

  useEffect(() => { load() }, [load])

  async function connect() {
    setLoading(true); setError('')
    try {
      const res = await slackConnect()
      setStatus({ connected: true, workspace_name: res.workspace_name })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to connect')
    } finally { setLoading(false) }
  }

  async function disconnect() {
    setLoading(true); setError('')
    try { await slackDisconnect(); setStatus({ connected: false }) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed to disconnect') }
    finally { setLoading(false) }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-lg bg-[#4A154B] flex items-center justify-center text-lg">
          <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white">
            <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Slack</h3>
          <p className="text-xs text-white/50">Chat with the agent by @mentioning the bot</p>
        </div>
        {status?.connected && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Connected
          </span>
        )}
      </div>

      {status?.connected ? (
        <div className="space-y-3">
          <div className="rounded-lg bg-white/5 px-4 py-2.5 text-sm text-white/70">
            Workspace: <span className="text-white font-medium">{status.workspace_name}</span>
          </div>
          <p className="text-xs text-white/40">
            @mention the bot in any channel to start a conversation. Sessions appear in the dashboard chat history.
          </p>
          <button
            onClick={disconnect}
            disabled={loading}
            className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Disconnecting…' : 'Disconnect Slack'}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-white/50">
            Make sure <code className="bg-white/10 px-1 rounded">SLACK_BOT_TOKEN</code> and{' '}
            <code className="bg-white/10 px-1 rounded">SLACK_APP_TOKEN</code> are set in the backend,
            then click Connect to link this workspace to your account.
          </p>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            onClick={connect}
            disabled={loading}
            className="rounded-lg bg-[#4A154B] hover:bg-[#611f69] text-white text-sm font-medium px-4 py-2 transition-colors disabled:opacity-50"
          >
            {loading ? 'Connecting…' : 'Connect Slack Workspace'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Telegram section ──────────────────────────────────────────────────────────

function TelegramSection() {
  const [status, setStatus] = useState<{ connected: boolean; chat_id?: string } | null>(null)
  const [codeInfo, setCodeInfo] = useState<{ code: string; instruction: string; bot_username: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try { setStatus(await telegramStatus()) } catch { /* token not configured */ }
  }, [])

  useEffect(() => { load() }, [load])

  // Poll for connection after code is generated
  useEffect(() => {
    if (!codeInfo || status?.connected) return
    const interval = setInterval(async () => {
      const s = await telegramStatus().catch(() => null)
      if (s?.connected) { setStatus(s); setCodeInfo(null); clearInterval(interval) }
    }, 3000)
    return () => clearInterval(interval)
  }, [codeInfo, status?.connected])

  async function generateCode() {
    setLoading(true); setError('')
    try {
      const res = await telegramGenerateCode()
      setCodeInfo(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to generate code')
    } finally { setLoading(false) }
  }

  async function disconnect() {
    setLoading(true); setError('')
    try { await telegramDisconnect(); setStatus({ connected: false }); setCodeInfo(null) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed to disconnect') }
    finally { setLoading(false) }
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-lg bg-[#229ED9] flex items-center justify-center">
          <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white">
            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Telegram</h3>
          <p className="text-xs text-white/50">Chat with the agent directly in Telegram</p>
        </div>
        {status?.connected && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Connected
          </span>
        )}
      </div>

      {status?.connected ? (
        <div className="space-y-3">
          <div className="rounded-lg bg-white/5 px-4 py-2.5 text-sm text-white/70">
            Chat ID: <span className="text-white font-medium font-mono">{status.chat_id}</span>
          </div>
          <p className="text-xs text-white/40">
            Message the bot directly in Telegram. Conversations sync to the dashboard chat history.
          </p>
          <button
            onClick={disconnect}
            disabled={loading}
            className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Disconnecting…' : 'Disconnect Telegram'}
          </button>
        </div>
      ) : codeInfo ? (
        <div className="space-y-3">
          <div className="rounded-lg bg-white/5 border border-white/10 px-4 py-3 space-y-2">
            <p className="text-xs text-white/60">{codeInfo.instruction}</p>
            <div className="flex items-center gap-2">
              <code className="text-2xl font-mono font-bold tracking-widest text-white">
                {codeInfo.code}
              </code>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/40">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            Waiting for you to send the code in Telegram…
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-white/50">
            Make sure <code className="bg-white/10 px-1 rounded">TELEGRAM_BOT_TOKEN</code> is set
            and the webhook is registered, then generate a code to link your Telegram account.
          </p>
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button
            onClick={generateCode}
            disabled={loading}
            className="rounded-lg bg-[#229ED9] hover:bg-[#1a7fb5] text-white text-sm font-medium px-4 py-2 transition-colors disabled:opacity-50"
          >
            {loading ? 'Generating…' : 'Connect Telegram'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function SettingsPanel() {
  return (
    <div className="flex-1 overflow-y-auto bg-[#0d0d0d] p-6">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <h1 className="text-xl font-semibold text-white">Settings</h1>
          <p className="text-sm text-white/40 mt-1">Connect external channels and integrations to your agents</p>
        </div>

        {/* Messaging channels */}
        <div className="space-y-3">
          <h2 className="text-xs font-semibold text-white/40 uppercase tracking-wider">Channels</h2>
          <SlackSection />
          <TelegramSection />

          <div className="rounded-xl border border-white/10 bg-white/5 p-5 opacity-50">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-[#25D366] flex items-center justify-center text-lg">
                <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">WhatsApp</h3>
                <p className="text-xs text-white/50">Coming soon</p>
              </div>
              <span className="ml-auto text-xs text-white/30 bg-white/5 px-2 py-0.5 rounded-full">
                Soon
              </span>
            </div>
          </div>
        </div>

        {/* MCP Integrations */}
        <div className="space-y-3">
          <div>
            <h2 className="text-xs font-semibold text-white/40 uppercase tracking-wider">MCP Integrations</h2>
            <p className="text-xs text-white/25 mt-1">
              Connect external services. Agents with the integration enabled can call these tools at runtime.
            </p>
          </div>
          <MCPSection />
        </div>
      </div>
    </div>
  )
}
