'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'
import { syncUser } from '@/lib/api'

const SYNCED_KEY = 'ollive-user-synced'

async function ensureSynced(session: Session | null) {
  if (typeof window === 'undefined') return
  const token = session?.access_token
  const uid = session?.user?.id
  if (!token || !uid) return
  if (sessionStorage.getItem(SYNCED_KEY) === uid) return
  try {
    await syncUser(token)
    sessionStorage.setItem(SYNCED_KEY, uid)
  } catch (e) {
    console.error('Background user sync failed:', e)
  }
}

interface AuthContextValue {
  session: Session | null
  user: User | null
  accessToken: string | null
  loading: boolean
  signInWithGoogle: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
      ensureSynced(data.session)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s)
      if (event === 'SIGNED_IN') ensureSynced(s)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signInWithGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: { prompt: 'select_account' },
      },
    })
  }

  const signOut = async () => {
    await supabase.auth.signOut()
    if (typeof window !== 'undefined') sessionStorage.removeItem(SYNCED_KEY)
    setSession(null)
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        accessToken: session?.access_token ?? null,
        loading,
        signInWithGoogle,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
