import { useEffect, useRef } from 'react'
import type { Target } from '../types'

type Props = {
  targets: Target[]
  liveTarget: string | null
  registerSocket: (id: string, node: HTMLElement | null) => void
}

export function JackField({ targets, liveTarget, registerSocket }: Props) {
  const fieldRef = useRef<HTMLElement>(null)

  // On the phone strip, keep the jack that's answering in view.
  useEffect(() => {
    if (!liveTarget) return
    const jack = fieldRef.current?.querySelector(`[data-jack="${liveTarget}"]`)
    jack?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
  }, [liveTarget])

  return (
    <nav ref={fieldRef} className="jack-field" aria-label="Lines Orin can put you through to">
      <div className="nameplate">
        <span className="nameplate-word">Orin</span>
        <span className="nameplate-sub">one ask · the right line</span>
      </div>
      <ul className="jacks">
        {targets.map((target) => {
          const live = target.id === liveTarget
          return (
            <li
              key={target.id}
              className="jack"
              data-jack={target.id}
              data-available={target.available}
              data-live={live || undefined}
            >
              <span className="lamp" aria-hidden="true" />
              <span className="jack-plate">
                <span className="jack-name">{target.name}</span>
                <span className="jack-meta">
                  {target.cost === 'free' ? 'Free · open weights' : 'Paid'}
                  <span className="visually-hidden">
                    {target.available ? ', available' : `, unavailable: ${target.reason}`}
                    {live ? ', answering now' : ''}
                  </span>
                </span>
                {!target.available && (
                  <span className="jack-reason" aria-hidden="true">
                    {target.reason}
                  </span>
                )}
              </span>
              <span
                className="socket"
                aria-hidden="true"
                ref={(node) => registerSocket(target.id, node)}
              />
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
