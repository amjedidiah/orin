import { useEffect, useState } from 'react'

type ProviderStatus = 'ok' | 'error' | 'not_configured'

type Health = {
  status: 'ok'
  meta_api: ProviderStatus
}

const statusLabel: Record<ProviderStatus, string> = {
  ok: 'connected',
  error: 'unreachable',
  not_configured: 'no API key set',
}

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<Health>
      })
      .then(setHealth)
      .catch(() => setFailed(true))
  }, [])

  return (
    <main className="shell">
      <h1>Orin</h1>
      <p className="tagline">
        Ask once. Orin picks the best-fit model or agent and brings the answer back.
      </p>
      <output className="status">
        {failed && 'Backend unreachable'}
        {!failed && !health && 'Checking backend…'}
        {health && `Backend ok · Meta Model API ${statusLabel[health.meta_api]}`}
      </output>
    </main>
  )
}

export default App
