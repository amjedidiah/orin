import type { ChatEvent, StoredConversation, Target } from './types'

const TOKEN_KEY = 'orin.ownerToken'
const TOKEN_COOKIE = 'orin_owner_token'

export class Unauthorized extends Error {}

const COOKIE_MAX_AGE = 60 * 60 * 24 * 365

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

// <img> requests can't send headers, so images authenticate with this cookie. It lasts as
// long as the stored key, so past images still load after a browser restart.
function writeCookie(token: string) {
  const secure = location.protocol === 'https:' ? '; Secure' : ''
  document.cookie =
    `${TOKEN_COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=${COOKIE_MAX_AGE}; ` +
    `SameSite=Strict${secure}`
}

export function saveToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Private mode: the cookie still carries the key.
  }
  writeCookie(token)
}

/** Re-issue the image cookie from the stored key (e.g. after it expired or was cleared). */
export function syncTokenCookie() {
  const token = readToken()
  if (token) writeCookie(token)
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing stored.
  }
  document.cookie = `${TOKEN_COOKIE}=; Path=/; Max-Age=0; SameSite=Strict`
}

function headers(extra: Record<string, string> = {}): HeadersInit {
  const token = readToken()
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: headers(init.headers as Record<string, string>),
  })
  if (response.status === 401) throw new Unauthorized()
  if (!response.ok) throw new Error(`${path} failed with HTTP ${response.status}`)
  return response
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
    headers: { 'Content-Type': 'application/json' },
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
