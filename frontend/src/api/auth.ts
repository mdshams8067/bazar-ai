import { apiRequest } from './client'
import type { Token, User } from '../types/api'

export interface SignupPayload {
  email: string
  password: string
  name: string
  phone?: string
}

export function signup(payload: SignupPayload): Promise<Token> {
  return apiRequest<Token>('/auth/signup', { method: 'POST', body: payload })
}

export function login(email: string, password: string): Promise<Token> {
  // POST /auth/login is form-encoded (OAuth2PasswordRequestForm), not
  // JSON — `username` is the field name FastAPI expects, holding the email.
  return apiRequest<Token>('/auth/login', {
    method: 'POST',
    form: { username: email, password },
  })
}

export function getMe(): Promise<User> {
  return apiRequest<User>('/auth/me')
}
