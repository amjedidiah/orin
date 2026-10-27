export type Target = {
  id: string
  name: string
  output: 'text' | 'image'
  cost: 'paid' | 'free'
  strengths: string[]
  available: boolean
  reason: string | null
}

export type Fallback = { from: string; to: string; reason: string }

export type Route = {
  target: string
  reason: string
  alternatives: string[]
  steps: { target: string; instruction: string }[]
  routed_by: 'router' | 'default'
}

export type StepView = {
  id: string
  target: string
  servedBy: string | null
  text: string
  imageUrl: string | null
  fallbacks: Fallback[]
  error: string | null
}

export type Turn = {
  key: string
  number: number | null
  prompt: string
  route: Route | null
  steps: StepView[]
  status: 'routing' | 'answering' | 'done'
}

export type ChatEvent =
  | ({ type: 'route' } & Route)
  | {
      type: 'step_start'
      index: number
      target: string
      name: string
      cost: 'paid' | 'free'
      served_by: string
    }
  | { type: 'token'; index: number; text: string }
  | { type: 'image'; index: number; url: string }
  | ({ type: 'fallback'; index: number } & Fallback)
  | { type: 'step_error'; index: number; reason: string }
  | { type: 'done'; conversation_id: string; number: number }

export type StoredConversation = {
  id: string
  number: number
  prompt: string
  response: string
  route: Route
  steps: {
    target: string
    served_by: string | null
    output: string
    image_url: string | null
    fallbacks: Fallback[]
    error: string | null
  }[]
  created_at: string
}
