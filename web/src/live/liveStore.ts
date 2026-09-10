import { useSyncExternalStore } from 'react'

export interface LiveState {
  connected: boolean
  mock: boolean
  lastEventAt: Record<string, number>
  lastPotEventAt: Record<string, number>
  lastMessageAt: number
}

let state: LiveState = { connected: false, mock: false, lastEventAt: {}, lastPotEventAt: {}, lastMessageAt: 0 }
const listeners = new Set<() => void>()

function emit() { for (const l of listeners) l() }

export const liveStore = {
  get: () => state,
  set(patch: Partial<LiveState>) {
    state = { ...state, ...patch }
    emit()
  },
  touch(topic: string, pot?: string | null) {
    const now = Date.now()
    state = {
      ...state,
      lastMessageAt: now,
      lastEventAt: { ...state.lastEventAt, [topic]: now },
      lastPotEventAt: pot ? { ...state.lastPotEventAt, [pot]: now } : state.lastPotEventAt,
    }
    emit()
  },
  subscribe(l: () => void) {
    listeners.add(l)
    return () => { listeners.delete(l) }
  },
}

export function useLiveStore(): LiveState {
  return useSyncExternalStore(liveStore.subscribe, liveStore.get, liveStore.get)
}
