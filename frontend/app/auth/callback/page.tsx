'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { syncUser } from '@/lib/api'

export default function AuthCallbackPage() {
  const router = useRouter()

  useEffect(() => {
    const handle = async () => {
      const params = new URL(window.location.href).searchParams
      const code = params.get('code')
      const error = params.get('error')

      if (error) {
        console.error('OAuth error:', error)
        router.replace('/login')
        return
      }

      if (code) {
        await supabase.auth.exchangeCodeForSession(code)
      }

      // Read the session after exchange — reliable even if detectSessionInUrl
      // already consumed the code before this useEffect ran.
      const { data: { session } } = await supabase.auth.getSession()

      if (session?.access_token) {
        try {
          await syncUser(session.access_token)
        } catch (e) {
          console.error('Sync failed:', e)
        }
      }

      router.replace('/')
    }

    handle()
  }, [router])

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
      <div className="w-5 h-5 rounded-full border-2 border-white/20 border-t-white animate-spin" />
    </div>
  )
}
