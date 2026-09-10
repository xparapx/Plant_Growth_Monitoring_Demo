import type { LiveEvent } from '@/api/types'
import { API_BASE, MOCK } from '@/api/client'
import { liveStore } from './liveStore'

type Handler = (ev: LiveEvent) => void
const handlers = new Set<Handler>()
let socket: WebSocket | null = null
let retry = 1000
let pingTimer: number | undefined
let reconnectTimer: number | undefined
let started = false

function url(): string {
  if (API_BASE) return API_BASE.replace(/^http/, 'ws') + '/ws'
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws`
}

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return
  try {
    socket = new WebSocket(url())
  } catch {
    scheduleReconnect()
    return
  }
  socket.onopen = () => {
    retry = 1000
    liveStore.set({ connected: true })
    window.clearInterval(pingTimer)
    pingTimer = window.setInterval(() => { try { socket?.send(JSON.stringify({ type: 'ping' })) } catch { /* ignore */ } }, 25_000)
  }
  socket.onmessage = (m) => {
    let ev: LiveEvent
    try { ev = JSON.parse(m.data) } catch { return }
    if (ev.type === 'pong') return
    for (const h of handlers) h(ev)
  }
  socket.onclose = () => {
    liveStore.set({ connected: false })
    window.clearInterval(pingTimer)
    scheduleReconnect()
  }
  socket.onerror = () => { try { socket?.close() } catch { /* ignore */ } }
}

function scheduleReconnect() {
  window.clearTimeout(reconnectTimer)
  reconnectTimer = window.setTimeout(connect, retry)
  retry = Math.min(retry * 2, 30_000)
}

export function startLive() {
  if (started) return
  started = true
  if (MOCK) {
    liveStore.set({ mock: true })
    import('@/mock').then((m) => m.startMockLive((ev) => { for (const h of handlers) h(ev) }))
    return
  }
  connect()
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') connect() })
}

export function onLive(h: Handler): () => void {
  handlers.add(h)
  return () => { handlers.delete(h) }
}
