/* Time helpers for the mock: ISO-Z stamps, tz-local parts, ISO weeks, and db.py bucketing. */

export const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z')

const fmts = new Map<string, Intl.DateTimeFormat>()
function fmt(tz: string): Intl.DateTimeFormat {
  let f = fmts.get(tz)
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
    fmts.set(tz, f)
  }
  return f
}

export interface Parts { y: number; m: number; d: number; h: number; mi: number }

export function localParts(ms: number, tz: string): Parts {
  const p: Record<string, number> = {}
  for (const x of fmt(tz).formatToParts(new Date(ms))) if (x.type !== 'literal') p[x.type] = Number(x.value)
  return { y: p.year, m: p.month, d: p.day, h: p.hour === 24 ? 0 : p.hour, mi: p.minute }
}

const pad = (n: number) => String(n).padStart(2, '0')
export const localDay = (ms: number, tz: string) => { const p = localParts(ms, tz); return `${p.y}-${pad(p.m)}-${pad(p.d)}` }
export const localHour = (ms: number, tz: string) => localParts(ms, tz).h

/** Local wall-clock (y, m, d, h, mi) in tz -> UTC ms. */
export function zonedToUtc(y: number, m: number, d: number, h: number, mi: number, tz: string): number {
  const guess = Date.UTC(y, m - 1, d, h, mi)
  const p = localParts(guess, tz)
  const asUtc = Date.UTC(p.y, p.m - 1, p.d, p.h, p.mi)
  return guess - (asUtc - guess)
}

/** Next occurrence of local HH:MM in tz, strictly after now. */
export function nextOccurrence(hhmm: string, tz: string, now = Date.now()): number {
  const [h, mi] = hhmm.split(':').map(Number)
  const p = localParts(now, tz)
  let t = zonedToUtc(p.y, p.m, p.d, h, mi, tz)
  if (t <= now) t = zonedToUtc(p.y, p.m, p.d + 1, h, mi, tz)
  return t
}

export function isoWeek(day: string): string {
  const [y, m, d] = day.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d))
  const dayNum = (date.getUTCDay() + 6) % 7
  date.setUTCDate(date.getUTCDate() - dayNum + 3)
  const firstThu = new Date(Date.UTC(date.getUTCFullYear(), 0, 4))
  const week = 1 + Math.round(((date.getTime() - firstThu.getTime()) / 86400000 - 3 + ((firstThu.getUTCDay() + 6) % 7)) / 7)
  return `${date.getUTCFullYear()}-W${pad(week)}`
}

export function addMinutes(hhmm: string, mins: number): string {
  const [h, mi] = hhmm.split(':').map(Number)
  const t = (h * 60 + mi + mins) % 1440
  return `${pad(Math.floor(t / 60))}:${pad(t % 60)}`
}

// ---- bucketing (db.py) --------------------------------------------------------
export const BUCKETS: Record<string, number> = { raw: 0, '5m': 300, '15m': 900, '1h': 3600, '6h': 21600, '1d': 86400 }

export function autoBucket(spanS: number, points = 600): number {
  for (const b of [300, 900, 3600, 10800, 21600, 86400]) if (spanS / b <= points) return b
  return 86400
}

export function bucketSeconds(bucket: string, fromMs: number | null, toMs: number | null, points = 600): number {
  if (bucket === 'auto') return autoBucket(fromMs !== null && toMs !== null ? (toMs - fromMs) / 1000 : 7 * 86400, points)
  if (!(bucket in BUCKETS)) throw new Error('bad_bucket')
  return BUCKETS[bucket]
}

export interface Bucketed { ts: number; n: number; vals: Record<string, number | null> }

/** Mean per bucket (+ count n).  bucketS == 0 returns the rows as they are (n = 1). */
export function resample<T extends { ts: number }>(rows: T[], cols: string[], bucketS: number): Bucketed[] {
  const R = rows as unknown as (Record<string, unknown> & { ts: number })[]
  if (bucketS <= 0) {
    return [...R].sort((a, b) => a.ts - b.ts).map((r) => ({ ts: r.ts, n: 1, vals: Object.fromEntries(cols.map((c) => [c, num(r[c])])) }))
  }
  const acc = new Map<number, { n: number; sum: Record<string, number>; cnt: Record<string, number> }>()
  for (const r of R) {
    const b = Math.floor(r.ts / 1000 / bucketS) * bucketS * 1000
    let a = acc.get(b)
    if (!a) { a = { n: 0, sum: {}, cnt: {} }; acc.set(b, a) }
    a.n++
    for (const c of cols) {
      const v = num(r[c])
      if (v === null) continue
      a.sum[c] = (a.sum[c] ?? 0) + v
      a.cnt[c] = (a.cnt[c] ?? 0) + 1
    }
  }
  return [...acc.entries()].sort((a, b) => a[0] - b[0]).map(([ts, a]) => ({
    ts, n: a.n, vals: Object.fromEntries(cols.map((c) => [c, a.cnt[c] ? a.sum[c] / a.cnt[c] : null])),
  }))
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

export const round = (v: number, d = 2) => { const k = 10 ** d; return Math.round(v * k) / k }
