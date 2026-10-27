import { type RefObject, useEffect, useState } from 'react'

type Props = {
  boardRef: RefObject<HTMLElement | null>
  logRef: RefObject<HTMLElement | null>
  socket: HTMLElement | null
  plug: HTMLElement | null
  /** Changes whenever the cord should swing in again (new call or a re-patch). */
  patchKey: string
}

type Geometry = { d: string; plugX: number; plugY: number; socketX: number; socketY: number }

function measure(board: HTMLElement, log: HTMLElement, socket: HTMLElement, plug: HTMLElement) {
  const origin = board.getBoundingClientRect()
  const view = log.getBoundingClientRect()
  const s = socket.getBoundingClientRect()
  const p = plug.getBoundingClientRect()
  const plugY = p.top + p.height / 2
  // Only draw while the plug end is on screen inside the call log.
  if (plugY < view.top + 8 || plugY > view.bottom - 8) return null

  const socketX = s.left + s.width / 2 - origin.left
  const socketY = s.top + s.height / 2 - origin.top
  const plugX = p.left - origin.left - 2
  const endY = plugY - origin.top
  const span = Math.max(plugX - socketX, 40)
  // A cord hangs: both handles drop below the straight line, more when the run is long.
  const sag = Math.min(140, 30 + span * 0.35)
  const d =
    `M ${socketX} ${socketY} ` +
    `C ${socketX + span * 0.35} ${socketY + sag}, ${plugX - span * 0.4} ${endY + sag}, ${plugX} ${endY}`
  return { d, plugX, plugY: endY, socketX, socketY }
}

export function Cord({ boardRef, logRef, socket, plug, patchKey }: Props) {
  const [geometry, setGeometry] = useState<Geometry | null>(null)

  useEffect(() => {
    const board = boardRef.current
    const log = logRef.current
    if (!board || !log || !socket || !plug) {
      setGeometry(null)
      return
    }
    let frame = 0
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setGeometry(measure(board, log, socket, plug)))
    }
    update()
    const resize = new ResizeObserver(update)
    resize.observe(board)
    resize.observe(plug)
    // A jack plate that grows (e.g. an "unavailable" reason) moves the sockets below it.
    resize.observe(socket.closest('.jacks') ?? socket)
    log.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      cancelAnimationFrame(frame)
      resize.disconnect()
      log.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [boardRef, logRef, socket, plug])

  if (!geometry) return null
  return (
    <svg className="cord-layer" aria-hidden="true">
      <g key={patchKey} className="cord">
        <path className="cord-shadow" d={geometry.d} pathLength={1} />
        <path className="cord-line" d={geometry.d} pathLength={1} />
        <circle className="cord-plug" cx={geometry.socketX} cy={geometry.socketY} r={5} />
        <circle className="cord-plug" cx={geometry.plugX} cy={geometry.plugY} r={4} />
      </g>
    </svg>
  )
}
