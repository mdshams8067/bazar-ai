import { create } from 'zustand'
import { getMe } from '../api/auth'
import { supabase } from '../lib/supabaseClient'
import type { User } from '../types/api'

interface SignupPayload {
  email: string
  password: string
  name: string
  phone?: string
}

interface AuthState {
  user: User | null
  status: 'idle' | 'loading' | 'ready'
  error: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (payload: SignupPayload) => Promise<void>
  logout: () => Promise<void>
  /** Restores the session from Supabase's own persisted session on app load. */
  restore: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: 'idle',
  error: null,

  async login(email, password) {
    set({ status: 'loading', error: null })
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw new Error(error.message)
      const user = await getMe()
      set({ user, status: 'ready' })
    } catch (err) {
      set({ status: 'ready', error: err instanceof Error ? err.message : 'Login failed' })
      throw err
    }
  },

  async signup(payload) {
    set({ status: 'loading', error: null })
    try {
      const { data, error } = await supabase.auth.signUp({
        email: payload.email,
        password: payload.password,
        // Read back by the backend from the verified token's claims to
        // fill in the profile row on first request (core/security.py) —
        // not stored as a separate field by us, Supabase carries it.
        options: { data: { name: payload.name, phone: payload.phone } },
      })
      if (error) throw new Error(error.message)
      if (!data.session) {
        // "Confirm email" is on in this Supabase project's Auth settings
        // — signUp succeeded, but there's no session until the customer
        // clicks the confirmation link, so there's nothing to log in yet.
        throw new Error('Check your email to confirm your account, then sign in.')
      }
      const user = await getMe()
      set({ user, status: 'ready' })
    } catch (err) {
      set({ status: 'ready', error: err instanceof Error ? err.message : 'Signup failed' })
      throw err
    }
  },

  async logout() {
    await supabase.auth.signOut()
    set({ user: null })
  },

  async restore() {
    set({ status: 'loading' })
    const {
      data: { session },
    } = await supabase.auth.getSession()
    if (!session) {
      set({ user: null, status: 'ready' })
      return
    }
    try {
      const user = await getMe()
      set({ user, status: 'ready' })
    } catch {
      set({ user: null, status: 'ready' })
    }
  },
}))
