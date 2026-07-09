import { useEffect, useState } from 'react'
import { checkHealth } from '../../api/health'

// Free-tier backend cold starts ~50s after inactivity. Rather than a blank
// screen while the first request hangs, ping /health (cheap, no DB call)
// and show a friendly "waking up" banner until it responds — polling,
// not a fixed timer, since cold-start length varies.
export function ColdStartBanner() {
  const [state, setState] = useState<'checking' | 'warm' | 'waking'>('checking')

  useEffect(() => {
    let cancelled = false
    let attempt = 0

    async function poll() {
      const ok = await checkHealth(attempt === 0 ? 2500 : 6000)
      if (cancelled) return
      if (ok) {
        setState('warm')
        return
      }
      setState('waking')
      attempt += 1
      setTimeout(poll, 3000)
    }

    poll()
    return () => {
      cancelled = true
    }
  }, [])

  if (state !== 'waking') return null

  return (
    <div className="bg-accent-blue-tint px-4 py-2 text-center text-sm text-accent-blue">
      Waking up the server — first load can take up to a minute on the free tier. Hang tight…
    </div>
  )
}
