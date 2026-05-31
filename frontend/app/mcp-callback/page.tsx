'use client'

import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

function MCPCallbackInner() {
  const params = useSearchParams()

  useEffect(() => {
    const connected = params.get('mcp_connected')
    const error = params.get('mcp_error')

    if (window.opener) {
      window.opener.postMessage(
        { type: 'mcp_oauth_result', connected, error },
        window.location.origin,
      )
      window.close()
    } else {
      // Popup was blocked — OAuth ran in same tab. Go back to root with param
      // so ChatInterface can detect it and open the settings panel.
      const q = connected ? `mcp_connected=${connected}` : `mcp_error=${error}`
      window.location.href = `/?${q}`
    }
  }, [params])

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
      <div className="text-center space-y-3">
        <div className="w-10 h-10 rounded-full border-2 border-white/20 border-t-white animate-spin mx-auto" />
        <p className="text-sm text-white/50">Completing connection…</p>
      </div>
    </div>
  )
}

export default function MCPCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-2 border-white/20 border-t-white animate-spin" />
      </div>
    }>
      <MCPCallbackInner />
    </Suspense>
  )
}
