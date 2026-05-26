'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'

export default function AuthCallbackPage() {
  const router = useRouter()

  useEffect(() => {
    supabase.auth.exchangeCodeForSession(window.location.search).then(() => {
      router.replace('/')
    })
  }, [router])

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center">
      <div className="w-5 h-5 rounded-full border-2 border-white/20 border-t-white animate-spin" />
    </div>
  )
}
