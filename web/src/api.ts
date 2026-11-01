import type { ChatEvent, StoredConversation, Target } from './types'

const LEGACY_TOKEN_KEY = 'orin.ownerToken'
const LEGACY_TOKEN_COOKIE = 'orin_owner_token'
const JSON_HEADERS = { 'Content-Type': 'application/json' }

export class Unauthorized extends Error {}
export class RateLimited extends Error {}
export class NotConfigured extends Error {}

/** Earlier versions kept the raw owner token where page scripts could read it. Erase it. */
export function forgetLegacyToken() {
  try {
    localStorage.removeItem(LEGACY_TOKEN_KEY)
  } catch {
    // Storage is blocked, so nothing was stored.
  }
  document.cookie = `${LEGACY_TOKEN_COOKIE}=; Path=/; Max-Age=0; SameSite=Strict`
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`/api${path}`, init)
  if (response.status === 401) throw new Unauthorized()
  if (response.status === 429) throw new RateLimited()
  if (response.status === 503) throw new NotConfigured()
  if (!response.ok) throw new Error(`${path} failed with HTTP ${response.status}`)
  return response
}

/** Swap the owner key for an HttpOnly session cookie; the key itself is never stored. */
export async function createSession(token: string): Promise<void> {
  await request('/session', {
    method: 'POST',
    body: JSON.stringify({ token }),
    headers: JSON_HEADERS,
  })
}

export async function endSession(): Promise<void> {
  await request('/session', { method: 'DELETE' })
}

export async function fetchSessionRequired(): Promise<boolean> {
  const { required } = (await (await request('/session')).json()) as { required: boolean }
  return required
}

export async function fetchTargets(): Promise<Target[]> {
  return (await request('/targets')).json()
}

export async function fetchHistory(limit = 50): Promise<StoredConversation[]> {
  return (await request(`/history?limit=${limit}`)).json()
}

/** POST a message and yield each server-sent event as it arrives. */
export async function* streamChat(message: string, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
  const response = await request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message }),
    headers: JSON_HEADERS,
    signal,
  })
  if (!response.body) throw new Error('The answer stream did not open.')
  yield* readEvents(response.body)
}

/** Parse a server-sent event body into chat events. */
export async function* readEvents(
  body: ReadableStream<Uint8Array<ArrayBuffer>>,
): AsyncGenerator<ChatEvent> {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    // SSE allows CRLF line endings; normalise so block boundaries are always "\n\n".
    buffer += value.replace(/\r\n?/g, '\n')
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const data = block
        .split('\n')
        .filter((line) => line.startsWith('data: '))
        .map((line) => line.slice(6))
        .join('\n')
      if (data) yield JSON.parse(data) as ChatEvent
      boundary = buffer.indexOf('\n\n')
    }
  }
}
