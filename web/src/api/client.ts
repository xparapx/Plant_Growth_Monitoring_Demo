export class ApiError extends Error {
  status: number
  code: string
  details: unknown
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export const MOCK: boolean =
  import.meta.env.VITE_MOCK === '1' ||
  (typeof location !== 'undefined' && new URLSearchParams(location.search).get('mock') === '1')

export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

export interface FetchInit {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  headers?: Record<string, string>
}

export async function apiFetch<T>(path: string, init: FetchInit = {}): Promise<T> {
  if (MOCK) {
    const { mockFetch } = await import('@/mock')
    return mockFetch<T>(path, init)
  }
  const res = await fetch(API_BASE + path, {
    method: init.method ?? 'GET',
    headers: { ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(init.headers ?? {}) },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    signal: init.signal,
    credentials: 'same-origin',
  })
  if (!res.ok) {
    let body: { error?: { code?: string; message?: string; details?: unknown } } = {}
    try { body = await res.json() } catch { /* not json */ }
    throw new ApiError(res.status, body.error?.code ?? 'http_error', body.error?.message ?? res.statusText, body.error?.details)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** Absolute URL for images/streams (mock mode swaps in data URIs). */
export function assetUrl(path: string): string {
  return API_BASE + path
}
