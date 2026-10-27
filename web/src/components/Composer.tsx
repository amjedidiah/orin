import { ArrowUp } from 'lucide-react'
import { type FormEvent, type KeyboardEvent, useRef, useState } from 'react'

type Props = {
  busy: boolean
  onSend: (message: string) => void
}

export function Composer({ busy, onSend }: Props) {
  const [draft, setDraft] = useState('')
  const formRef = useRef<HTMLFormElement>(null)
  const ready = draft.trim().length > 0 && !busy

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (!ready) return
    onSend(draft.trim())
    setDraft('')
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form className="line-key" ref={formRef} onSubmit={submit}>
      <label className="visually-hidden" htmlFor="ask">
        Ask Orin
      </label>
      <textarea
        id="ask"
        rows={1}
        value={draft}
        placeholder="Ask anything. Orin picks the line."
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
        maxLength={8000}
      />
      <button type="submit" className="send" disabled={!ready} aria-label="Put the call through">
        <ArrowUp aria-hidden="true" size={20} strokeWidth={2.25} />
      </button>
    </form>
  )
}
