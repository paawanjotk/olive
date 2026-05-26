'use client'

import { useState, useEffect, useRef } from 'react'

// Adaptive drain rate — keeps the buffer non-empty between LLM chunk arrivals
// so there is never a visible pause while waiting for the next network batch.
//
//  buffer > FAST_THRESHOLD  →  FAST_RATE chars/frame  (catch up after big burst)
//  buffer ≤ FAST_THRESHOLD  →  SLOW_RATE chars/frame  (crawl ≈ LLM chunk cadence)
//
// At 60 fps:
//   1 char/frame  ≈  60 chars/sec   ← comfortable reading speed, buffer stays warm
//   3 chars/frame ≈ 180 chars/sec   ← catches up without looking like a dump
const SLOW_RATE       = 1   // chars/frame when buffer is nearly empty
const FAST_RATE       = 3   // chars/frame when a large burst just arrived
const FAST_THRESHOLD  = 20  // chars in buffer that trigger fast mode

/**
 * Smoothly animates incoming streaming text so it appears character-by-character
 * instead of in irregular network-sized bursts.
 *
 * @param source  Full accumulated text from the store (grows as chunks arrive)
 * @param active  Whether streaming is still in progress.
 *                When false the remaining buffer is flushed instantly so the
 *                final message snaps to complete without waiting for animation.
 */
export function useSmoothedText(source: string, active: boolean): string {
  const [displayed, setDisplayed] = useState('')
  const pendingRef   = useRef('')          // chars queued but not yet displayed
  const prevSrcRef   = useRef('')          // last source value we processed
  const rafRef       = useRef<number | null>(null)

  // ── Queue new characters whenever source grows ───────────────────────────
  useEffect(() => {
    if (source === '') {
      // Source was reset (new turn / cleared) — wipe everything immediately
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      pendingRef.current = ''
      prevSrcRef.current = ''
      setDisplayed('')
      return
    }

    const newChars = source.slice(prevSrcRef.current.length)
    if (newChars) {
      prevSrcRef.current = source
      pendingRef.current += newChars
    }

    // Start the drain loop if it isn't already running
    if (rafRef.current === null && pendingRef.current.length > 0) {
      const tick = () => {
        if (pendingRef.current.length === 0) {
          rafRef.current = null
          return
        }
        // Adaptive rate: drain faster when a big burst arrived so we don't
        // fall behind, but slow down when the buffer is nearly empty so we
        // never outpace the LLM and create empty-buffer pauses.
        const rate  = pendingRef.current.length > FAST_THRESHOLD ? FAST_RATE : SLOW_RATE
        const take  = Math.min(rate, pendingRef.current.length)
        const chars = pendingRef.current.slice(0, take)
        pendingRef.current = pendingRef.current.slice(take)
        setDisplayed(prev => prev + chars)
        rafRef.current = requestAnimationFrame(tick)
      }
      rafRef.current = requestAnimationFrame(tick)
    }
  }, [source])

  // ── Flush buffer instantly when streaming ends ───────────────────────────
  useEffect(() => {
    if (!active && pendingRef.current.length > 0) {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      setDisplayed(prev => prev + pendingRef.current)
      pendingRef.current = ''
    }
  }, [active])

  // ── Cleanup on unmount ───────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return displayed
}
