'use client'

import { useEffect, useRef, useCallback, useState } from 'react'

const WS_BASE =
  process.env.NEXT_PUBLIC_BACKEND_WS_URL || 'ws://localhost:8000'

interface UseWebSocketOptions {
  clientId: string
  onMessage: (data: unknown) => void
  onConnect?: () => void
  onDisconnect?: () => void
}

interface UseWebSocketReturn {
  sendMessage: (payload: unknown) => void
  isConnected: boolean
}

export function useWebSocket({
  clientId,
  onMessage,
  onConnect,
  onDisconnect,
}: UseWebSocketOptions): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const maxReconnectAttempts = 5
  const isMountedRef = useRef(true)

  const onMessageRef = useRef(onMessage)
  const onConnectRef = useRef(onConnect)
  const onDisconnectRef = useRef(onDisconnect)

  // Keep refs updated so callbacks always have current values
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])
  useEffect(() => {
    onConnectRef.current = onConnect
  }, [onConnect])
  useEffect(() => {
    onDisconnectRef.current = onDisconnect
  }, [onDisconnect])

  const connect = useCallback(() => {
    if (!isMountedRef.current) return
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    const wsUrl = `${WS_BASE}/api/v1/ws/chat/${clientId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      if (!isMountedRef.current) return
      reconnectAttemptsRef.current = 0
      setIsConnected(true)
      onConnectRef.current?.()
    }

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return
      try {
        const data = JSON.parse(event.data as string)
        onMessageRef.current(data)
      } catch (err) {
        console.error('WebSocket: failed to parse message', err)
      }
    }

    ws.onclose = (event) => {
      if (!isMountedRef.current) return
      setIsConnected(false)
      onDisconnectRef.current?.()

      // Attempt reconnect with exponential backoff
      if (
        reconnectAttemptsRef.current < maxReconnectAttempts &&
        !event.wasClean
      ) {
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttemptsRef.current),
          16000
        )
        reconnectAttemptsRef.current += 1
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) connect()
        }, delay)
      }
    }

    ws.onerror = (event) => {
      console.error('WebSocket error:', event)
    }
  }, [clientId])

  useEffect(() => {
    isMountedRef.current = true
    connect()

    return () => {
      isMountedRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted')
        wsRef.current = null
      }
    }
  }, [connect])

  const sendMessage = useCallback((payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    } else {
      console.warn('WebSocket is not connected, cannot send message')
    }
  }, [])

  return { sendMessage, isConnected }
}
