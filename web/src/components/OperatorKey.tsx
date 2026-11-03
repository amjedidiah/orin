import { KeyRound } from 'lucide-react'
import { type FormEvent, useState } from 'react'

type Props = {
  /** False when the server has no usable ORIN_OWNER_TOKEN, so no key can unlock it. */
  configured: boolean
  failed: boolean
  busy: boolean
  /** A connection problem, shown instead of a key rejection. */
  error: string | null
  onSubmit: (token: string) => void
}

export function OperatorKey({ configured, failed, busy, error, onSubmit }: Props) {
  const [token, setToken] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (token.trim() && !busy) onSubmit(token.trim())
  }

  if (!configured) {
    return (
      <section className="operator-key" aria-labelledby="not-set-up-title">
        <KeyRound aria-hidden="true" size={28} className="operator-key-icon" />
        <h1 id="not-set-up-title" className="operator-key-title">
          This board isn't set up
        </h1>
        <p className="operator-key-copy">
          Set <code>ORIN_OWNER_TOKEN</code> on the server, at least 32 characters, then reload
          this page.
        </p>
      </section>
    )
  }

  return (
    <form className="operator-key" onSubmit={submit}>
      <KeyRound aria-hidden="true" size={28} className="operator-key-icon" />
      <h1 className="operator-key-title">This board is locked</h1>
      <p className="operator-key-copy">
        Enter the owner key set as <code>ORIN_OWNER_TOKEN</code> on this instance.
      </p>
      <label htmlFor="owner-key" className="field-label">
        Owner key
      </label>
      <input
        id="owner-key"
        type="password"
        autoComplete="current-password"
        value={token}
        onChange={(event) => setToken(event.target.value)}
        aria-invalid={failed || undefined}
        aria-describedby={failed ? 'owner-key-error' : undefined}
      />
      {failed && (
        <p id="owner-key-error" className="line-error" role="alert">
          That key didn't fit. Check the ORIN_OWNER_TOKEN value and try again.
        </p>
      )}
      {error && (
        <p className="line-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" className="plug-in" disabled={!token.trim() || busy}>
        {busy ? 'Unlocking…' : 'Unlock the board'}
      </button>
    </form>
  )
}
