'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import { OliveLogo } from '@/components/Logo'

export default function LoginPage() {
  const { signInWithGoogle, session, loading } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [signingIn, setSigningIn] = useState(false)

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    if (!loading && session) router.replace('/')
  }, [session, loading, router])

  if (loading) return <div className="min-h-screen bg-[#0d0d0d]" />

  const handleSignIn = async () => {
    try {
      setSigningIn(true)
      await signInWithGoogle()
    } catch {
      setSigningIn(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0d0d0d] flex items-center justify-center px-4">
      {/* Atmospheric background */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/2 h-[620px] w-[620px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,_rgba(16,163,127,0.12),_transparent_62%)] blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(to_bottom,_transparent_30%,_rgba(0,0,0,0.45))]" />
      </div>

      <div
        className={cn(
          'relative w-full max-w-[380px] transition-all duration-700 ease-out',
          mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        )}
      >
        {/* Brand + heading */}
        <div className="mb-7 flex flex-col items-center gap-3.5">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.08] ring-1 ring-white/[0.06] shadow-[0_8px_30px_rgba(0,0,0,0.45)]">
            <OliveLogo size={28} className="text-emerald-400" />
          </div>
          <div className="text-center">
            <h1 className="text-white text-[22px] font-semibold tracking-tight leading-tight">
              Welcome to Ollive
            </h1>
            <p className="mt-1.5 text-sm text-white/40">
              Build and orchestrate AI agent workflows
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-white/[0.07] bg-[#141414]/80 backdrop-blur-sm p-6 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.7)]">
          <button
            onClick={handleSignIn}
            disabled={signingIn}
            className="group w-full flex items-center justify-center gap-3 rounded-xl bg-white px-4 py-3 text-sm font-medium text-[#1a1a1a] transition-all hover:bg-white/90 active:scale-[0.99] disabled:opacity-70 disabled:active:scale-100"
          >
            {signingIn ? (
              <span className="h-[18px] w-[18px] animate-spin rounded-full border-2 border-[#1a1a1a]/25 border-t-[#1a1a1a]" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" className="flex-shrink-0">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            )}
            {signingIn ? 'Redirecting…' : 'Continue with Google'}
          </button>

          <p className="mt-5 text-center text-xs leading-relaxed text-white/25">
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-white/20">
          Multi-agent orchestration, made visual.
        </p>
      </div>
    </div>
  )
}
