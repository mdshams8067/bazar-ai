import { apiRequest } from './client'
import type { User } from '../types/api'

// No signup/login here — those go straight through Supabase's own client
// (see store/authStore.ts), not this backend. This is the one auth-related
// call that still hits our own API: resolving the verified token to this
// user's app-specific profile (name/phone — Supabase owns email/password).
export function getMe(): Promise<User> {
  return apiRequest<User>('/auth/me')
}
