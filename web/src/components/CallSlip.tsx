import { ChevronRight, CircleAlert, Plug, Repeat2 } from 'lucide-react'
import { Fragment, useId } from 'react'
import Markdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import { activeStepIndex } from '../board'
import type { Target, Turn } from '../types'

// Models often separate lines with single newlines; keep them as line breaks.
const REMARK_PLUGINS = [remarkBreaks]

type Props = {
  turn: Turn
  names: Map<string, Target>
  registerPlug?: (node: HTMLElement | null) => void
}

function nameOf(names: Map<string, Target>, id: string) {
  return names.get(id)?.name ?? id
}

export function CallSlip({ turn, names, registerPlug }: Props) {
  const headingId = useId()
  const route = turn.route
  const activeIndex = activeStepIndex(turn)
  const active = turn.steps[activeIndex]
  const free = active ? names.get(active.target)?.cost === 'free' : false
  const multiStep = turn.steps.length > 1
  // After a re-patch the route reason explains the original pick, so name it.
  const repatched = turn.steps.some((step) => step.fallbacks.length > 0)

  return (
    <article className="call" aria-labelledby={headingId} aria-busy={turn.status !== 'done'}>
      <div className="ask-slip">
        <h2 id={headingId} className="call-number">
          {turn.number === null ? 'Call' : `Call ${turn.number}`}
          <span className="visually-hidden">: {turn.prompt}</span>
        </h2>
        <p className="ask-text">{turn.prompt}</p>
      </div>

      <div className="answer-slip">
        <div className="patch">
          <span className="patch-plug" ref={registerPlug}>
            <Plug className="patch-icon" aria-hidden="true" size={16} strokeWidth={2} />
          </span>
          {route ? (
            <span className="patch-label">
              Put through to{' '}
              {turn.steps.map((step, i) => (
                <Fragment key={step.id}>
                  {i > 0 && <span className="chain-arrow"> then </span>}
                  {i === activeIndex ? (
                    <strong>{nameOf(names, step.target)}</strong>
                  ) : (
                    <span className="chain-other">{nameOf(names, step.target)}</span>
                  )}
                </Fragment>
              ))}
              {active?.servedBy && <span className="served-by"> · {active.servedBy}</span>}
              {free && <span className="free-tag">Free</span>}
            </span>
          ) : (
            <span className="patch-label patch-pending">Finding the right line…</span>
          )}
          {route && (
            <p className="patch-reason">
              {repatched &&
                `Routed to ${route.steps.map((step) => nameOf(names, step.target)).join(' then ')}: `}
              {route.reason}
            </p>
          )}
        </div>

        {route && (route.alternatives.length > 0 || multiStep || route.routed_by === 'default') && (
          <details className="why">
            <summary>
              <ChevronRight className="summary-chevron" aria-hidden="true" size={15} />
              Alternatives and steps
            </summary>
            {route.alternatives.length > 0 && (
              <p className="why-alts">
                Also fit: {route.alternatives.map((id) => nameOf(names, id)).join(', ')}
              </p>
            )}
            {multiStep && (
              <ol className="why-steps">
                {turn.steps.map((step, i) => (
                  <li key={step.id}>
                    <strong>{nameOf(names, step.target)}</strong>:{' '}
                    {route.steps[i]?.instruction}
                  </li>
                ))}
              </ol>
            )}
            {route.routed_by === 'default' && (
              <p className="why-alts">The router couldn't decide, so Orin used its default line.</p>
            )}
          </details>
        )}

        {turn.steps.map((step, index) => {
          const last = index === turn.steps.length - 1
          return (
            <section key={step.id} className="step" data-last={last || undefined}>
              {step.fallbacks.map((fallback) => (
                <p key={`${fallback.from}>${fallback.to}`} className="repatch">
                  <Repeat2 aria-hidden="true" size={15} />
                  Re-patched from {nameOf(names, fallback.from)} to {nameOf(names, fallback.to)}:{' '}
                  {fallback.reason}
                </p>
              ))}
              {multiStep && !last && step.text && (
                <details className="draft">
                  <summary>
                    <ChevronRight className="summary-chevron" aria-hidden="true" size={15} />
                    {nameOf(names, step.target)} wrote the brief
                  </summary>
                  <p>{step.text}</p>
                </details>
              )}
              {(last || !multiStep) && step.text && (
                <div className="answer-text">
                  <Markdown remarkPlugins={REMARK_PLUGINS}>{step.text}</Markdown>
                </div>
              )}
              {step.imageUrl && (
                <img
                  className="answer-image"
                  src={step.imageUrl}
                  alt={`Drawn by ${nameOf(names, step.target)} for: ${turn.prompt}`}
                />
              )}
              {step.error && (
                <p className="line-error" role="alert">
                  <CircleAlert aria-hidden="true" size={16} />
                  {step.error}
                </p>
              )}
            </section>
          )
        })}
        {turn.status === 'answering' && !turn.steps.some((s) => s.text || s.imageUrl) && (
          <p className="ringing">Ringing…</p>
        )}
      </div>
    </article>
  )
}
