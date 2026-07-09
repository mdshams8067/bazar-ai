import { API_BASE_URL } from './client'

// Free-tier hosting (Render/Railway) cold-starts ~50s after inactivity —
// this is a cheap, no-DB-call endpoint so the app can show a "waking up
// the server…" state instead of a blank screen on the first request.
export async function checkHealth(timeoutMs = 4000): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)
    const res = await fetch(`${API_BASE_URL}/health`, { signal: controller.signal })
    clearTimeout(timeout)
    return res.ok
  } catch {
    return false
  }
}
