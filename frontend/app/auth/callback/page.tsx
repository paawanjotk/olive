'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { syncUser } from '@/lib/api'

export default function AuthCallbackPage() {
  const router = useRouter()

  useEffect(() => {
    let done = false
    let unsubscribe: (() => void) | null = null

    const finish = async (accessToken: string) => {
      if (done) return
      done = true
      unsubscribe?.()
      try {
        await syncUser(accessToken)
      } catch (e) {
        console.error('Sync failed:', e)
      }
      router.replace('/')
    }

    const handle = async () => {
      const params = new URL(window.location.href).searchParams
      const error = params.get('error')
      if (error) {
        console.error('OAuth error:', error)
        router.replace('/login')
        return
      }

      // Don't manually exchange the code — detectSessionInUrl already does it.
      // A second exchange races with the auto-detect and throws (PKCE codes
      // are one-time-use), aborting this handler before syncUser runs.
      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        (_event, session) => {
          if (session?.access_token) finish(session.access_token)
        },
      )
      unsubscribe = () => subscription.unsubscribe()

      // Cover the case where auto-detect finished before the listener attached.
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) finish(session.access_token)

      // Fail-safe: if neither the listener nor getSession produced a session
      // within a few seconds, bail back to login rather than spinning forever.
      setTimeout(() => {
        if (!done) {
          console.error('Auth callback timed out without a session')
          done = true
          unsubscribe?.()
          router.replace('/login')
        }
      }, 8000)
    }

    handle()
    return () => {
      done = true
      unsubscribe?.()
    }
  }, [router])

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
      <div className="w-5 h-5 rounded-full border-2 border-white/20 border-t-white animate-spin" />
    </div>
  )
}
