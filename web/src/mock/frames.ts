/* Frames (db.py) + roster (analytics/roster.py) for the mock. */
import type { Meta, TableName } from '@/api/types'
import { iso } from './time'

export interface SoilRow { ts: number; node: string; plant_id: string; treat: string | null; raw: number | null; pct: number | null; n: number }
export interface PumpRow {
  ts: number; node: string; plant_id: string; treat: string | null; dur_ms: number | null; soil_before: number | null; soil_after: number | null
  raw_before: number | null; raw_after: number | null; shots: number; reason: string | null
}
export interface GrowRow {
  ts: number; plant_id: string; treat: string | null; phase: 'dawn' | 'pm'; area_cm2: number | null; area_px: number
  px_per_cm: number; img_file: string; ok: number; contour: [number, number][] | null
}
export interface EnvRow { ts: number; node: string; temp: number | null; hum: number | null; press: number | null; vpd: number | null; lux: number | null; co2: number | null; n: number }

export interface Frames {
  env: EnvRow[]; soil: SoilRow[]; pump: PumpRow[]; grow: GrowRow[]
  fake: TableName[]; real_pots: Set<string>; real_env: boolean
  now: number | null; now_real: number | null; tz: string
}

export const TREATS = ['stable', 'fluct']

export interface Roster {
  treat: Record<string, string>; pots: string[]; groups: Record<string, string[]>
  unknown: string[]; conflicts: Record<string, Record<string, string>>; sources: Record<string, Record<string, string>>; ncol: number
}

function lastTreat(rows: { plant_id: string; treat: string | null }[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const r of rows) if (r.treat !== null && r.treat !== undefined) out[r.plant_id] = String(r.treat)
  return out
}

export function buildRoster(soil: SoilRow[], grow: GrowRow[]): Roster {
  let treat = lastTreat([...soil, ...grow])
  const unknown = [...new Set(Object.values(treat).filter((v) => !TREATS.includes(v)))].sort()
  if (unknown.length) treat = Object.fromEntries(Object.entries(treat).filter(([, v]) => TREATS.includes(v)))
  const sources: Record<string, Record<string, string>> = {}
  for (const [src, rows] of [['soil', soil], ['growth', grow]] as const) {
    for (const [pid, tr] of Object.entries(lastTreat(rows))) (sources[pid] ??= {})[src] = tr
  }
  const conflicts = Object.fromEntries(Object.entries(sources).filter(([, v]) => new Set(Object.values(v)).size > 1))
  if (Object.keys(conflicts).length) treat = Object.fromEntries(Object.entries(treat).filter(([k]) => !(k in conflicts)))
  const pots = Object.keys(treat).sort()
  const groups: Record<string, string[]> = {}
  for (const t of TREATS) { const g = pots.filter((p) => treat[p] === t); if (g.length) groups[t] = g }
  return { treat, pots, groups, unknown, conflicts, sources, ncol: Math.max(1, ...Object.values(groups).map((g) => g.length)) }
}

export function suggestedSql(r: Roster): string | null {
  if (!r.unknown.length) return null
  const labels = r.unknown.map((u) => "'" + u + "'").join(', ')
  return `DELETE FROM soil WHERE treat IN (${labels});`
}

export const maxTs = (...lists: { ts: number }[][]): number | null => {
  let m: number | null = null
  for (const l of lists) for (const r of l) if (m === null || r.ts > m) m = r.ts
  return m
}

export function meta(fr: Frames): Meta {
  return { now: fr.now === null ? null : iso(fr.now), now_real: fr.now_real === null ? null : iso(fr.now_real), dummy: [...fr.fake].sort() }
}

export const emptyFrames = (tz: string): Frames => ({ env: [], soil: [], pump: [], grow: [], fake: [], real_pots: new Set(), real_env: false, now: null, now_real: null, tz })
