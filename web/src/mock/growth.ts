/* TS ports of analytics/growth.py and analytics/irrigation.py. */
import type { Canopy, Droop, DroopTimeline, PlantConfig, PumpRecentRow, Rgr, SilFrame, Silhouettes, Water } from '@/api/types'
import { mean, sd } from './analytics'
import type { Frames, GrowRow, Roster } from './frames'
import { iso, localDay, round } from './time'

const DAY = 86_400_000
const byTs = <T extends { ts: number }>(a: T, b: T) => a.ts - b.ts
const dawnRows = (fr: Frames) => fr.grow.filter((r) => r.phase === 'dawn')
const potRows = (rows: GrowRow[], p: string) => rows.filter((r) => r.plant_id === p).sort(byTs)

export function canopySeries(fr: Frames, roster: Roster, phase = 'dawn'): Pick<Canopy, 'pots'> {
  const g = phase === 'all' ? fr.grow : fr.grow.filter((r) => r.phase === phase)
  const pots: Canopy['pots'] = []
  for (const p of roster.pots) {
    const d = potRows(g, p)
    if (!d.length) continue
    pots.push({ plant_id: p, treat: roster.treat[p] ?? null, ts: d.map((r) => iso(r.ts)), area_cm2: d.map((r) => (r.area_cm2 === null ? null : round(r.area_cm2, 2))) })
  }
  return { pots }
}

export function silhouettes(fr: Frames, roster: Roster): Pick<Silhouettes, 'pots' | 'not_enough'> {
  const dawn = dawnRows(fr)
  const out: Pick<Silhouettes, 'pots' | 'not_enough'> = { pots: [], not_enough: [] }
  if (!dawn.length) { out.not_enough = [...roster.pots]; return out }
  const frame = (r: GrowRow): SilFrame => ({ ts: iso(r.ts), area_cm2: r.area_cm2 === null ? null : round(r.area_cm2, 2), area_px: r.area_px, contour: r.contour ?? [] })
  for (const [treat, members] of Object.entries(roster.groups)) {
    for (const p of members) {
      const d = potRows(dawn, p).filter((r) => r.contour !== null)
      if (d.length < 2) { out.not_enough.push(p); continue }
      const nw = d[d.length - 1]
      const older = d.filter((r) => r.ts <= nw.ts - DAY)
      const old = older.length ? older[older.length - 1] : d[0]
      const base = d[0]
      const lim = nw.contour?.length ? Math.max(...nw.contour.flat().map(Math.abs)) * 1.12 : 1
      out.pots.push({
        plant_id: p, treat, new: frame(nw), old: frame(old),
        gain_pct: old.area_px ? round((100 * (nw.area_px - old.area_px)) / old.area_px, 1) : null, gap_d: round((nw.ts - old.ts) / DAY, 2),
        base: { ts: iso(base.ts), area_cm2: base.area_cm2 === null ? null : round(base.area_cm2, 2) },
        total_pct: base.area_px ? round((100 * (nw.area_px - base.area_px)) / base.area_px, 1) : null, span_d: round((nw.ts - base.ts) / DAY, 2), lim: round(lim, 1),
      })
    }
  }
  return out
}

/** pivot_table(index=[day, plant_id], columns=phase, values=area_px).dropna() -> day -> pot -> droop % */
function droopPivot(fr: Frames, tz: string): Map<string, Map<string, { dawn: number; pm: number; droop: number }>> {
  const acc = new Map<string, Map<string, { dawn: number[]; pm: number[] }>>()
  for (const r of fr.grow) {
    const day = localDay(r.ts, tz)
    let byPot = acc.get(day)
    if (!byPot) { byPot = new Map(); acc.set(day, byPot) }
    let cell = byPot.get(r.plant_id)
    if (!cell) { cell = { dawn: [], pm: [] }; byPot.set(r.plant_id, cell) }
    cell[r.phase].push(r.area_px)
  }
  const out = new Map<string, Map<string, { dawn: number; pm: number; droop: number }>>()
  for (const day of [...acc.keys()].sort()) {
    const m = new Map<string, { dawn: number; pm: number; droop: number }>()
    for (const [pid, c] of acc.get(day)!) {
      if (!c.dawn.length || !c.pm.length) continue
      const dawn = mean(c.dawn), pm = mean(c.pm)
      m.set(pid, { dawn, pm, droop: (100 * (dawn - pm)) / dawn })
    }
    if (m.size) out.set(day, m)
  }
  return out
}

export function droop(fr: Frames, roster: Roster, cfg: PlantConfig): Pick<Droop, 'rows' | 'missing' | 'has_both_phases'> {
  const out: Pick<Droop, 'rows' | 'missing' | 'has_both_phases'> = { rows: [], missing: [...roster.pots], has_both_phases: false }
  const phases = new Set(fr.grow.map((r) => r.phase))
  if (!fr.grow.length || !phases.has('dawn') || !phases.has('pm')) return out
  out.has_both_phases = true
  const pv = droopPivot(fr, cfg.tz)
  const lastDay = new Map<string, string>()
  for (const [day, m] of pv) for (const pid of m.keys()) lastDay.set(pid, day)
  const have = roster.pots.filter((p) => lastDay.has(p))
  out.rows = have.map((p) => {
    const day = lastDay.get(p)!, c = pv.get(day)!.get(p)!
    return { pot: p, treat: roster.treat[p] ?? null, day, dawn_px: Math.floor(c.dawn), pm_px: Math.floor(c.pm), droop_pct: round(c.droop, 2) }
  })
  out.missing = roster.pots.filter((p) => !lastDay.has(p))
  return out
}

export function droopTimeline(fr: Frames, roster: Roster, cfg: PlantConfig, days = 14): Pick<DroopTimeline, 'days' | 'pots'> {
  if (!fr.grow.length) return { days: [], pots: [] }
  const pv = droopPivot(fr, cfg.tz)
  const allDays = [...pv.keys()].slice(-days)
  if (!allDays.length) return { days: [], pots: [] }
  const seen = new Set<string>()
  for (const m of pv.values()) for (const p of m.keys()) seen.add(p)
  return {
    days: allDays,
    pots: roster.pots.filter((p) => seen.has(p)).map((p) => ({ plant_id: p, treat: roster.treat[p] ?? null, droop_pct: allDays.map((d) => { const v = pv.get(d)!.get(p); return v === undefined ? null : round(v.droop, 2) }) })),
  }
}

export function rgr(fr: Frames, roster: Roster): Pick<Rgr, 'pots' | 'groups' | 'cohens_d' | 'effect' | 'worst_r2' | 'comparable'> {
  const dawn = dawnRows(fr)
  const rows: Rgr['pots'] = []
  for (const p of roster.pots) {
    const d = potRows(dawn, p).filter((r) => r.area_cm2 !== null && r.area_cm2 > 0)
    if (d.length < 3) continue
    const t = d.map((r) => (r.ts - d[0].ts) / DAY), y = d.map((r) => Math.log(r.area_cm2!))
    const tm = mean(t), ym = mean(y)
    const sxx = t.reduce((a, x) => a + (x - tm) ** 2, 0)
    const slope = t.reduce((a, x, i) => a + (x - tm) * (y[i] - ym), 0) / sxx
    const icpt = ym - slope * tm
    const sse = y.reduce((a, v, i) => a + (v - (slope * t[i] + icpt)) ** 2, 0)
    const se = t.length > 2 && sxx > 0 ? Math.sqrt(sse / (t.length - 2) / sxx) : NaN
    const sst = y.reduce((a, v) => a + (v - ym) ** 2, 0)
    const r2 = sst > 0 ? 1 - sse / sst : 1
    rows.push({ pot: p, treat: roster.treat[p] ?? null, rgr: round(slope, 5), se: Number.isNaN(se) ? null : round(se, 5), ci95: Number.isNaN(se) ? null : [round(slope - 1.96 * se, 5), round(slope + 1.96 * se, 5)], r2: round(r2, 4), n: t.length })
  }
  const out: ReturnType<typeof rgr> = { pots: rows, groups: {}, cohens_d: null, effect: null, worst_r2: null, comparable: false }
  if (!rows.length) return out
  for (const k of ['stable', 'fluct']) {
    const sub = rows.filter((r) => r.treat === k).map((r) => r.rgr)
    if (sub.length) out.groups[k] = { mean: round(mean(sub), 5), sd: sub.length < 2 ? null : round(sd(sub), 5), n: sub.length }
  }
  out.worst_r2 = round(Math.min(...rows.map((r) => r.r2)), 4)
  if (out.groups.stable && out.groups.fluct) {
    const a = rows.filter((r) => r.treat === 'stable').map((r) => r.rgr), b = rows.filter((r) => r.treat === 'fluct').map((r) => r.rgr)
    const pooled = Math.sqrt(((a.length > 1 ? sd(a) : 0) ** 2 + (b.length > 1 ? sd(b) : 0) ** 2) / 2)
    if (pooled && !Number.isNaN(pooled)) {
      const dEff = (mean(a) - mean(b)) / pooled
      out.cohens_d = round(dEff, 3)
      out.effect = Math.abs(dEff) >= 0.8 ? 'large' : Math.abs(dEff) >= 0.5 ? 'medium' : 'small'
    }
    out.comparable = true
  }
  return out
}

// ---- irrigation.py --------------------------------------------------------------
export const ML_PER_SEC = 10

export function pumpRecent(fr: Frames, roster: Roster, n = 5): { rows: PumpRecentRow[] } {
  const rows = [...fr.pump].sort((a, b) => b.ts - a.ts).slice(0, n).map((r) => {
    const before = r.soil_before === null ? null : round(r.soil_before, 1), after = r.soil_after === null ? null : round(r.soil_after, 1)
    return {
      ts: iso(r.ts), ago_h: fr.now === null ? null : Math.floor((fr.now - r.ts) / 3_600_000), pot: r.plant_id.toUpperCase(), plant_id: r.plant_id,
      treat: roster.treat[r.plant_id]?.toUpperCase() ?? null, pump_s: r.dur_ms === null ? null : round(r.dur_ms / 1000, 1),
      before, after, rise: before === null || after === null ? null : round(after - before, 1), reason: r.reason === null ? null : r.reason.replace(/_/g, ' '),
    }
  })
  return { rows }
}

export function waterSummary(fr: Frames, roster: Roster, tz: string, days = 14): Pick<Water, 'ml_per_s' | 'groups' | 'pots' | 'daily'> {
  const out: Pick<Water, 'ml_per_s' | 'groups' | 'pots' | 'daily'> = { ml_per_s: ML_PER_SEC, groups: {}, pots: [], daily: { days: [], groups: {} } }
  const p = fr.pump.filter((r) => r.dur_ms !== null && roster.treat[r.plant_id] !== undefined).map((r) => ({ ...r, ml: (r.dur_ms! / 1000) * ML_PER_SEC, treat: roster.treat[r.plant_id] }))
  if (!p.length) return out
  for (const k of [...new Set(p.map((r) => r.treat))].sort()) {
    const sub = p.filter((r) => r.treat === k), tot = sub.reduce((a, r) => a + r.ml, 0), np = new Set(sub.map((r) => r.plant_id)).size
    out.groups[k] = { total_ml: round(tot, 1), events: sub.length, pots: np, ml_per_pot: round(tot / Math.max(1, np), 1) }
  }
  for (const pid of roster.pots) {
    const sub = p.filter((r) => r.plant_id === pid).sort(byTs)
    if (!sub.length) continue
    const gaps = sub.slice(1).map((r, i) => (r.ts - sub[i].ts) / DAY)
    out.pots.push({ plant_id: pid, treat: roster.treat[pid] ?? null, events: sub.length, total_ml: round(sub.reduce((a, r) => a + r.ml, 0), 1), interval_d: gaps.map((g) => round(g, 2)), mean_interval_d: gaps.length ? round(mean(gaps), 2) : null, last_interval_d: gaps.length ? round(gaps[gaps.length - 1], 2) : null })
  }
  const daily = new Map<string, Record<string, number>>()
  for (const r of p) { const d = localDay(r.ts, tz); const row = daily.get(d) ?? {}; row[r.treat] = (row[r.treat] ?? 0) + r.ml; daily.set(d, row) }
  const ds = [...daily.keys()].sort().slice(-days)
  out.daily = { days: ds, groups: Object.fromEntries(Object.keys(out.groups).map((k) => [k, ds.map((d) => round(daily.get(d)![k] ?? 0, 1))])) }
  return out
}
