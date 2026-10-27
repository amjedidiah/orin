import type { ChatEvent, StepView, StoredConversation, Turn } from './types'

function emptyStep(target: string): StepView {
  return { id: crypto.randomUUID(), target, servedBy: null, text: '', imageUrl: null, fallbacks: [], error: null }
}

function updateStep(turn: Turn, index: number, change: (step: StepView) => StepView): Turn {
  return {
    ...turn,
    steps: turn.steps.map((step, i) => (i === index ? change(step) : step)),
  }
}

/** Apply one streamed event to the turn it belongs to. */
export function applyEvent(turn: Turn, event: ChatEvent): Turn {
  switch (event.type) {
    case 'route': {
      const { type: _type, ...route } = event
      return {
        ...turn,
        route,
        steps: route.steps.map((step) => emptyStep(step.target)),
        status: 'answering',
      }
    }
    case 'step_start':
      return updateStep(turn, event.index, (step) => ({
        ...step,
        target: event.target,
        servedBy: event.served_by,
      }))
    case 'token':
      return updateStep(turn, event.index, (step) => ({ ...step, text: step.text + event.text }))
    case 'image':
      return updateStep(turn, event.index, (step) => ({ ...step, imageUrl: event.url }))
    case 'fallback':
      return updateStep(turn, event.index, (step) => ({
        ...step,
        fallbacks: [...step.fallbacks, { from: event.from, to: event.to, reason: event.reason }],
      }))
    case 'step_error':
      return updateStep(turn, event.index, (step) => ({ ...step, error: event.reason }))
    case 'done':
      return { ...turn, number: event.number, status: 'done' }
  }
}

export function turnFromHistory(conversation: StoredConversation): Turn {
  return {
    key: conversation.id,
    number: conversation.number,
    prompt: conversation.prompt,
    route: conversation.route,
    steps: conversation.steps.map((step, index) => ({
      id: `${conversation.id}-${index}`,
      target: step.target,
      servedBy: step.served_by,
      text: step.output,
      imageUrl: step.image_url,
      fallbacks: step.fallbacks,
      error: step.error,
    })),
    status: 'done',
  }
}

export function newTurn(prompt: string): Turn {
  return { key: crypto.randomUUID(), number: null, prompt, route: null, steps: [], status: 'routing' }
}

/** The step currently (or last) on the line: the latest step a model has picked up. */
export function activeStepIndex(turn: Turn): number {
  const started = turn.steps.findLastIndex((step) => step.servedBy !== null)
  return Math.max(started, 0)
}

/** The jack a turn is patched into right now. */
export function patchedTarget(turn: Turn): string | null {
  return turn.steps[activeStepIndex(turn)]?.target ?? turn.route?.target ?? null
}
