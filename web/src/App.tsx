import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Unauthorized,
  clearToken,
  fetchHistory,
  fetchTargets,
  saveToken,
  streamChat,
  syncTokenCookie,
} from './api'
import { applyEvent, newTurn, patchedTarget, turnFromHistory } from './board'
import { CallSlip } from './components/CallSlip'
import { Composer } from './components/Composer'
import { Cord } from './components/Cord'
import { JackField } from './components/JackField'
import { OperatorKey } from './components/OperatorKey'
import type { ReplayLine } from './replay'
import type { Target, Turn } from './types'

const EXAMPLES = [
  'Write a launch announcement for my side project, with a headline and three key features.',
  "Translate 'We launch on Friday' into French.",
  'Make a launch banner for my side project.',
]

type Lock = 'open' | 'locked' | 'rejected'

type Line = Pick<ReplayLine, 'fetchTargets' | 'fetchHistory' | 'streamChat'>

const LIVE_LINE: Line = { fetchTargets, fetchHistory, streamChat }

// Dev only: `?replay=<name>` swaps the server for a labelled synthetic call (see replay.ts).
const REPLAY_NAME = import.meta.env.DEV ? new URLSearchParams(location.search).get('replay') : null

function App() {
  const [targets, setTargets] = useState<Target[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [lock, setLock] = useState<Lock>('open')
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [announcement, setAnnouncement] = useState('')
  const [replay, setReplay] = useState<ReplayLine | null>(null)
  const line = useRef<Line>(LIVE_LINE)

  const boardRef = useRef<HTMLDivElement>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const [sockets, setSockets] = useState<Record<string, HTMLElement>>({})
  const [plug, setPlug] = useState<HTMLElement | null>(null)
  const stickToBottom = useRef(true)

  const names = useMemo(() => new Map(targets.map((t) => [t.id, t])), [targets])

  const load = useCallback(async (attempt: Lock = 'open') => {
    try {
      if (import.meta.env.DEV && REPLAY_NAME) {
        const found = (await import('./replay')).replayLine(REPLAY_NAME)
        if (found) line.current = found
        setReplay(found)
      }
      const [nextTargets, history] = await Promise.all([
        line.current.fetchTargets(),
        line.current.fetchHistory(),
      ])
      setTargets(nextTargets)
      setTurns(history.reverse().map(turnFromHistory))
      setLock('open')
      setLoadError(null)
    } catch (error) {
      if (error instanceof Unauthorized) {
        setLock(attempt === 'rejected' ? 'rejected' : 'locked')
        setLoadError(null)
      } else {
        // A failed unlock attempt says nothing about the key; drop the stale rejection.
        setLock((current) => (current === 'rejected' ? 'locked' : current))
        setLoadError('Orin is unreachable right now. Check that the server is running, then reload.')
      }
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    syncTokenCookie()
    // Fetch on mount; every state update in `load` happens after an await.
    // oxlint-disable-next-line react/set-state-in-effect
    void load()
  }, [load])

  // Ref callbacks fire on every render; only a genuinely new node updates state.
  const registerSocket = useCallback((id: string, node: HTMLElement | null) => {
    if (!node) return
    setSockets((current) => (current[id] === node ? current : { ...current, [id]: node }))
  }, [])

  // Keep the newest call in view while it streams, unless the reader scrolled up.
  useEffect(() => {
    const log = logRef.current
    if (log && turns.length > 0 && stickToBottom.current) log.scrollTop = log.scrollHeight
  }, [turns])

  function onLogScroll() {
    const log = logRef.current
    if (log) stickToBottom.current = log.scrollHeight - log.scrollTop - log.clientHeight < 80
  }

  function unlock(token: string) {
    saveToken(token)
    setLoaded(false)
    void load('rejected')
  }

  async function send(message: string) {
    const turn = newTurn(message)
    const update = (change: (t: Turn) => Turn) =>
      setTurns((all) => all.map((t) => (t.key === turn.key ? change(t) : t)))
    setTurns((all) => [...all, turn])
    stickToBottom.current = true
    setBusy(true)
    setAnnouncement('Finding the right line.')
    try {
      for await (const event of line.current.streamChat(message)) {
        update((t) => applyEvent(t, event))
        if (event.type === 'step_start') {
          setAnnouncement(`Put through to ${event.name}.`)
        } else if (event.type === 'done') {
          setAnnouncement('Answer complete.')
        }
      }
    } catch (error) {
      if (error instanceof Unauthorized) {
        clearToken()
        setLock('locked')
        return
      }
      update((t) => ({
        ...t,
        status: 'done',
        steps: [
          ...t.steps,
          {
            id: crypto.randomUUID(),
            target: t.route?.target ?? 'orin',
            servedBy: null,
            text: '',
            imageUrl: null,
            fallbacks: [],
            error: 'The line dropped before the answer finished. Check your connection and ask again.',
          },
        ],
      }))
      setAnnouncement('The line dropped.')
    } finally {
      setBusy(false)
      line.current.fetchTargets().then(setTargets, () => undefined)
    }
  }

  const lastTurn = turns.at(-1)
  const patched = lastTurn ? patchedTarget(lastTurn) : null
  const liveTarget = lastTurn && lastTurn.status !== 'done' ? patched : null
  const socket = patched ? (sockets[patched] ?? null) : null
  const patchKey = lastTurn ? `${lastTurn.key}:${patched}` : ''

  if (lock !== 'open') {
    return (
      <main className="board board-locked">
        <OperatorKey failed={lock === 'rejected'} error={loadError} onSubmit={unlock} />
      </main>
    )
  }

  return (
    <div className="board" ref={boardRef}>
      <JackField targets={targets} liveTarget={liveTarget} registerSocket={registerSocket} />

      <main className="exchange">
        <h1 className="visually-hidden">Orin</h1>
        <div className="call-log" ref={logRef} onScroll={onLogScroll}>
          {import.meta.env.DEV && replay && (
            <p className="replay-flag" role="note">
              Synthetic replay · made-up data, no server
            </p>
          )}
          {!loaded && <p className="log-quiet">Warming up the board…</p>}
          {loadError && (
            <p className="line-error" role="alert">
              {loadError}
            </p>
          )}
          {loaded && !loadError && turns.length === 0 && (
            <div className="log-quiet">
              <p className="log-quiet-title">The board is quiet.</p>
              <p>Ask anything. Orin puts it through to the line that fits best and shows you why.</p>
              <ul className="examples">
                {(replay ? [replay.prompt] : EXAMPLES).map((example) => (
                  <li key={example}>
                    <button type="button" disabled={busy} onClick={() => void send(example)}>
                      {example}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {turns.map((turn, index) => (
            <CallSlip
              key={turn.key}
              turn={turn}
              names={names}
              registerPlug={index === turns.length - 1 ? setPlug : undefined}
            />
          ))}
        </div>
        <Composer busy={busy} onSend={(message) => void send(message)} />
      </main>

      <Cord boardRef={boardRef} logRef={logRef} socket={socket} plug={plug} patchKey={patchKey} />
      <output className="visually-hidden" aria-live="polite">
        {announcement}
      </output>
    </div>
  )
}

export default App
