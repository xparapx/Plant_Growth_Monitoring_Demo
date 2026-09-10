const nf = new Map<string, Intl.NumberFormat>()

export function fmtNum(v: number | null | undefined, digits = 1, opts: { sign?: boolean; group?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const key = `${digits}|${opts.sign ? 1 : 0}|${opts.group === false ? 0 : 1}`
  let f = nf.get(key)
  if (!f) {
    f = new Intl.NumberFormat('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits, signDisplay: opts.sign ? 'always' : 'auto', useGrouping: opts.group !== false })
    nf.set(key, f)
  }
  return f.format(v)
}

export function fmtPct(v: number | null | undefined, digits = 0, sign = false): string {
  return v === null || v === undefined ? '—' : `${fmtNum(v, digits, { sign })}%`
}

const timeFmt = new Intl.DateTimeFormat('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
const dtFmt = new Intl.DateTimeFormat('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
const dateFmt = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' })

const valid = (d: Date) => !Number.isNaN(d.getTime())
/** Formatters never throw: an unparseable input (e.g. a systemd 'Fri 2026-09-11 05:50:00 KST') is shown verbatim. */
export const fmtTimeLocal = (d: Date) => (valid(d) ? timeFmt.format(d).replace(/\s/g, '') : '—')
export const fmtDateTime = (iso: string | null | undefined) => { if (!iso) return '—'; const d = new Date(iso); return valid(d) ? dtFmt.format(d) : iso }
export const fmtDate = (iso: string | null | undefined) => { if (!iso) return '—'; const d = new Date(iso); return valid(d) ? dateFmt.format(d) : iso }
export const fmtHm = (iso: string | null | undefined) => { if (!iso) return '—'; const d = new Date(iso); return valid(d) ? timeFmt.format(d).replace(/\s/g, '') : iso }
export const fmtHms =(iso: string | null | undefined) => { if (!iso) return '—'; const d = new Date(iso); return valid(d) ? d.toLocaleTimeString('ko-KR', { hour12: false }) : iso }

export function fmtAgoMin(m: number | null | undefined): string {
  if (m === null || m === undefined) return '—'
  if (m < 60) return `${m}m`
  if (m < 60 * 48) return `${Math.floor(m / 60)}h ${m % 60}m`
  return `${Math.floor(m / 1440)}d`
}

export function fmtDuration(sec: number | null | undefined): string {
  if (sec === null || sec === undefined) return '—'
  const s = Math.max(0, Math.floor(sec))
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  if (d) return `${d}일 ${h}시간`
  if (h) return `${h}시간 ${m}분`
  return `${m}분 ${s % 60}초`
}

export function fmtBytes(b: number | null | undefined): string {
  if (b === null || b === undefined) return '—'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0, v = b
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
  return `${fmtNum(v, i ? 1 : 0)} ${u[i]}`
}

export const upper = (s: string | null | undefined) => (s ?? '').toUpperCase()
