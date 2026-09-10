/* In-process mock API for the GitHub Pages demo and offline design review.
   Filled in after the real pages exist; until then any mock request is an explicit error. */
import type { FetchInit } from '@/api/client'
import type { LiveEvent } from '@/api/types'

export async function mockFetch<T>(path: string, _init: FetchInit): Promise<T> {
  const { handle } = await import('./server')
  return handle<T>(path, _init)
}

export function startMockLive(emit: (ev: LiveEvent) => void): void {
  import('./server').then((m) => m.startLive(emit))
}
