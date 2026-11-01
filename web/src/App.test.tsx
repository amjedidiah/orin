import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const SYNTHETIC_KEY = 'synthetic-owner-key-for-tests-only'

type Reply = { status: number; body?: unknown }
type Routes = Record<string, Reply>

const OPEN_DATA: Routes = {
  'GET /api/targets': { status: 200, body: [] },
  'GET /api/history': { status: 200, body: [] },
}

function stubServer(routes: Routes) {
  const server = vi.fn(async (url: string, init: RequestInit = {}) => {
    const reply = routes[`${init.method ?? 'GET'} ${url.split('?')[0]}`] ?? { status: 404 }
    return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
      status: reply.status,
    })
  })
  vi.stubGlobal('fetch', server)
  return server
}

const LOCKED: Routes = {
  'GET /api/targets': { status: 401 },
  'GET /api/history': { status: 401 },
  'GET /api/session': { status: 200, body: { required: true } },
}

async function submitKey() {
  await screen.findByRole('heading', { name: 'This board is locked' })
  await userEvent.type(screen.getByLabelText('Owner key'), SYNTHETIC_KEY)
  await userEvent.click(screen.getByRole('button', { name: 'Unlock the board' }))
}

describe('owner session', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('erases a token left by an earlier version', async () => {
    localStorage.setItem('orin.ownerToken', SYNTHETIC_KEY)
    document.cookie = 'orin_owner_token=legacy; Path=/'
    stubServer(LOCKED)

    render(<App />)
    await screen.findByLabelText('Owner key')

    expect(localStorage.getItem('orin.ownerToken')).toBeNull()
    expect(document.cookie).not.toContain('orin_owner_token')
  })

  it('swaps the key for a session without storing it', async () => {
    const routes: Routes = { ...LOCKED, 'POST /api/session': { status: 204 } }
    const server = stubServer(routes)
    render(<App />)

    Object.assign(routes, OPEN_DATA)
    await submitKey()

    expect(await screen.findByRole('button', { name: 'Lock board' })).toBeEnabled()
    expect(server).toHaveBeenCalledWith(
      '/api/session',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ token: SYNTHETIC_KEY }) }),
    )
    expect(JSON.stringify(localStorage)).not.toContain(SYNTHETIC_KEY)
    expect(document.cookie).not.toContain(SYNTHETIC_KEY)
  })

  it.each([
    [401, "That key didn't fit"],
    [429, 'Too many tries'],
    [503, 'ORIN_OWNER_TOKEN is set'],
    [500, 'unreachable'],
  ])('shows why an unlock failed with HTTP %i', async (status, message) => {
    stubServer({ ...LOCKED, 'POST /api/session': { status } })
    render(<App />)

    await submitKey()

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('button', { name: 'Unlock the board' })).toBeEnabled()
  })

  it('tells the owner when the server has no usable token', async () => {
    stubServer({ 'GET /api/targets': { status: 503 }, 'GET /api/history': { status: 503 } })

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('at least 32 characters')
  })

  it('locks the board', async () => {
    const routes: Routes = {
      ...OPEN_DATA,
      'GET /api/session': { status: 200, body: { required: true } },
      'DELETE /api/session': { status: 204 },
    }
    stubServer(routes)
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Lock board' }))

    expect(await screen.findByLabelText('Owner key')).toBeInTheDocument()
  })

  it('stays open and reports the failure when locking fails', async () => {
    stubServer({
      ...OPEN_DATA,
      'GET /api/session': { status: 200, body: { required: true } },
      'DELETE /api/session': { status: 500 },
    })
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Lock board' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't lock the board")
    expect(screen.getByRole('button', { name: 'Lock board' })).toBeInTheDocument()
  })

  it('offers no lock on an instance without one', async () => {
    stubServer({ ...OPEN_DATA, 'GET /api/session': { status: 200, body: { required: false } } })

    render(<App />)

    await screen.findByText('The board is quiet.')
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Lock board' })).toBeNull())
  })

  it('explains a demo limit on the call that hit it', async () => {
    stubServer({
      ...OPEN_DATA,
      'GET /api/session': { status: 200, body: { required: false } },
      'POST /api/chat': { status: 429 },
    })
    render(<App />)
    await screen.findByText('The board is quiet.')

    await userEvent.type(screen.getByLabelText('Ask Orin'), 'hello{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('call limit')
  })
})
