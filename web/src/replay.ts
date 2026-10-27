// Dev-only synthetic replays, loaded with `?replay=<name>` under `bun run dev`.
// They stand in for the server so states that need a live outage (a re-patch, the
// free fallback) can be inspected without one. Everything here is made up.
import { readEvents } from './api'
import type { ChatEvent, StoredConversation, Target } from './types'

export type ReplayLine = {
  prompt: string
  fetchTargets: () => Promise<Target[]>
  fetchHistory: () => Promise<StoredConversation[]>
  streamChat: (message: string) => AsyncGenerator<ChatEvent>
}

type Replay = {
  prompt: string
  before: Target[]
  after: Target[]
  events: { delay: number; event: ChatEvent }[]
}

const SPARK: Target = {
  id: 'muse-spark',
  name: 'Muse Spark',
  output: 'text',
  cost: 'paid',
  strengths: ['multi-step reasoning', 'planning'],
  available: true,
  reason: null,
}

const SPARK_OPEN: Target = {
  id: 'muse-spark-open',
  name: 'Muse Spark Open',
  output: 'text',
  cost: 'free',
  strengths: ['quick answers', 'summaries'],
  available: true,
  reason: null,
}

const IMAGE: Target = {
  id: 'muse-image',
  name: 'Muse Image',
  output: 'image',
  cost: 'paid',
  strengths: ['image generation'],
  available: true,
  reason: null,
}

const ANSWER = `**Launch plan (synthetic replay)**

1. **Private beta, week 1.** Invite twenty early users. Risk: too few sign up; fix by posting in two communities you already belong to.
2. **Public launch, week 3.** Ship the landing page and announcement. Risk: the demo breaks on stage; record a fallback video.
3. **First paid users, week 6.** Turn on billing. Risk: pricing feels high; offer a launch discount for the first month.`

function tokens(text: string, delay: number): { delay: number; event: ChatEvent }[] {
  return text
    .split(/(?<=\s)/)
    .map((chunk) => ({ delay, event: { type: 'token', index: 0, text: chunk } }))
}

const REPLAYS: Record<string, Replay> = {
  // Muse Spark is picked, rate-limits on the call, and Muse Spark Open answers for free.
  fallback: {
    prompt: 'Plan my side project launch: three milestones, with one risk for each.',
    before: [SPARK, SPARK_OPEN, IMAGE],
    after: [{ ...SPARK, available: false, reason: 'rate limited' }, SPARK_OPEN, IMAGE],
    events: [
      {
        delay: 700,
        event: {
          type: 'route',
          target: 'muse-spark',
          reason: 'A plan with milestones and risks needs multi-step reasoning.',
          alternatives: ['muse-spark-open'],
          steps: [{ target: 'muse-spark', instruction: 'Write the launch plan.' }],
          routed_by: 'router',
        },
      },
      {
        delay: 1200,
        event: {
          type: 'fallback',
          index: 0,
          from: 'muse-spark',
          to: 'muse-spark-open',
          reason: 'rate limited',
        },
      },
      {
        delay: 600,
        event: {
          type: 'step_start',
          index: 0,
          target: 'muse-spark-open',
          name: 'Muse Spark Open',
          cost: 'free',
          served_by: 'Baseten',
        },
      },
      ...tokens(ANSWER, 35),
      { delay: 200, event: { type: 'done', conversation_id: 'replay-fallback', number: 1 } },
    ],
  },
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** Serialise the events as a server-sent event body, paced like a live answer. */
function sseBody(events: Replay['events']): ReadableStream<Uint8Array<ArrayBuffer>> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    async start(controller) {
      for (const { delay, event } of events) {
        await wait(delay)
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      }
      controller.close()
    },
  })
}

export function replayLine(name: string): ReplayLine | null {
  const replay = REPLAYS[name]
  if (!replay) return null
  let played = false
  return {
    prompt: replay.prompt,
    fetchTargets: async () => (played ? replay.after : replay.before),
    fetchHistory: async () => [],
    async *streamChat() {
      yield* readEvents(sseBody(replay.events))
      played = true
    },
  }
}
