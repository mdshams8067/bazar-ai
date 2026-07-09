import { create } from 'zustand'
import { getMe, login as apiLogin, signup as apiSignup, type SignupPayload } from '../api/auth'
import { clearToken, getToken, setToken } from '../lib/tokenStorage'
import type { User } from '../types/api'

interface AuthState {
  user: User | null
  status: 'idle' | 'loading' | 'ready'
  error: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (payload: SignupPayload) => Promise<void>
  logout: () => void
  /** Restores the session from a stored token on app load. */
  restore: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: 'idle',
  error: null,

  async login(email, password) {
    set({ status: 'loading', error: null })
    try {
      const token = await apiLogin(email, password)
      setToken(token.access_token)
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
      const token = await apiSignup(payload)
      setToken(token.access_token)
      const user = await getMe()
      set({ user, status: 'ready' })
    } catch (err) {
      set({ status: 'ready', error: err instanceof Error ? err.message : 'Signup failed' })
      throw err
    }
  },

  logout() {
    clearToken()
    set({ user: null })
  },

  async restore() {
    const token = getToken()
    if (!token) {
      set({ status: 'ready' })
      return
    }
    set({ status: 'loading' })
    try {
      const user = await getMe()
      set({ user, status: 'ready' })
    } catch {
      clearToken()
      set({ user: null, status: 'ready' })
    }
  },
}))
