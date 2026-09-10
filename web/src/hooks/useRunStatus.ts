import { useEffect, useState } from 'react'
import type { Summary } from '@/api/types'
import { ko } from '@/i18n/ko'

export const RUN_DAYS = 42

const timeFmt = new Intl.DateTimeFormat('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })

/** Day N/42 from `run_started`, online node count and a local clock — the header status strip. */
export function useRunStatus(s: Summary | undefined) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(id)
  }, [])
  const online = s ? s.nodes.filter((n) => n.real && n.state !== 'off').length : 0
  const total = s ? s.nodes.length : 0
  let day: number | null = null
  if (s?.run_started) {
    const t = new Date(s.run_started).getTime()
    if (!Number.isNaN(t)) day = Math.max(1, Math.floor((now - t) / 86_400_000) + 1)
  }
  const tzShort = s?.tz === 'Asia/Seoul' ? 'KST' : (s?.tz ?? '')
  const clock = `${timeFmt.format(new Date(now)).replace(/\s/g, '')}${tzShort ? ` ${tzShort}` : ''}`
  const parts = [ko.status.nodes(s ? (online || total) : 0), day === null ? ko.status.day(0, RUN_DAYS).replace('0/', '–/') : ko.status.day(day, RUN_DAYS), clock]
  return { online, total, day, text: parts.join(' · '), title: s?.run_started ? `run_started ${s.run_started}` : ko.status.notStarted }
}
