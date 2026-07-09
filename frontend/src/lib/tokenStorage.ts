// Single source of truth for the JWT, outside the store — avoids a
// store <-> client circular import (client attaches the header, store
// owns the "am I logged in" state derived from the same value).
const STORAGE_KEY = 'bazar_ai_token'

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY)
}
