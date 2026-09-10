/* Seeded port of analytics/dummy.py synth(): 7 days of soil / pump / growth / env rows. */
import type { PlantConfig } from '@/api/types'
import type { EnvRow, GrowRow, PumpRow, SoilRow } from './frames'
import { localHour, localParts, zonedToUtc } from './time'

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export class Rng {
  next: () => number
  constructor(seed: number) { this.next = mulberry32(seed) }
  uniform(a: number, b: number) { return a + (b - a) * this.next() }
  normal(mu = 0, sd = 1) {
    const u = Math.max(this.next(), 1e-12), v = this.next()
    return mu + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
  }
  int(a: number, b: number) { return Math.floor(this.uniform(a, b)) }
}

const r1 = (v: number) => Math.round(v * 10) / 10
const r2 = (v: number) => Math.round(v * 100) / 100

/** bands.band_pct(): (low %, high %) per treatment from the raw (wet, dry) bands + default calibration. */
export function bandPct(cfg: PlantConfig): Record<string, [number, number]> {
  const [dry, wet] = cfg.bands.cal_default
  const pctOf = (raw: number) => (100 * (dry - raw)) / (dry - wet)
  const out: Record<string, [number, number]> = {}
  for (const [t, [wetRaw, dryRaw]] of Object.entries(cfg.bands.raw)) {
    const lo = pctOf(dryRaw), hi = pctOf(wetRaw)
    out[t] = [Math.min(lo, hi), Math.max(lo, hi)]
  }
  return out
}

export function blob(R: number, seed: number, k = 9): [number, number][] {
  const r = new Rng(seed)
  const ph = r.uniform(0, 6.3), ph2 = r.uniform(0, 6.3)
  const out: [number, number][] = []
  for (let i = 0; i < 63; i++) {
    const a = i * 0.1
    const rad = R * (1 + 0.16 * Math.sin(k * a + ph) + 0.09 * Math.sin(2 * k * a + ph2))
    out.push([r1(rad * Math.cos(a)), r1(rad * Math.sin(a))])
  }
  return out
}

export interface Synth { soil: SoilRow[]; pump: PumpRow[]; grow: GrowRow[]; env: EnvRow[]; ts: number[] }

type Pot = [string, string, number, number]

export function synth(cfg: PlantConfig, roster: Record<string, string> | null = null, days = 7, stepMin = 30, seed = 7, nowMs = Date.now()): Synth {
  const rng = new Rng(seed)
  const band = bandPct(cfg)
  const n = Math.floor((days * 24 * 60) / stepMin)
  const stepMs = stepMin * 60_000
  const t0 = Math.floor(nowMs / 3_600_000) * 3_600_000 - stepMs * (n - 1)
  const ts = Array.from({ length: n }, (_, i) => t0 + stepMs * i)
  const hours = ts.map((t) => localHour(t, cfg.tz))

  const pots: Pot[] = roster
    ? Object.entries(roster).sort(([a], [b]) => (a < b ? -1 : 1)).map(([pid, tr]) => [pid, tr, ...(band[tr] ?? [30, 55])] as Pot)
    : ['stable', 'stable', 'stable', 'fluct', 'fluct', 'fluct'].map((t, i) => [`p${i + 1}`, t, band[t][0], band[t][1]] as Pot)

  const soil: SoilRow[] = [], pump: PumpRow[] = []
  pots.forEach(([pid, tr, on, off], k) => {
    let v = off - rng.uniform(0, 3), filling = false
    for (let i = 0; i < n; i++) {
      const hh = hours[i]
      const rate = (hh >= 7 && hh < 19 ? 0.55 : 0.12) * (1 + 0.1 * ((k % 3) - 1))
      if (filling) {
        v += 4.5
        if (v >= off) { v = off; filling = false }
      } else {
        v -= rate * (stepMin / 30) * rng.uniform(0.85, 1.15)
        if (v <= on) {
          filling = true
          pump.push({ ts: ts[i], node: 'dummy', plant_id: pid, treat: tr, dur_ms: rng.int(2400, 3600), soil_before: r1(v), soil_after: off, raw_before: null, raw_after: null, shots: 1, reason: 'filled' })
        }
      }
      soil.push({ ts: ts[i], node: 'dummy', plant_id: pid, treat: tr, raw: null, pct: r2(v + rng.normal(0, 0.25)), n: 30 })
    }
  })
  const ids = pots.map((p) => p[0])
  if (ids.length >= 5) {                                   // stuck-sensor demo
    const rows = soil.filter((r) => r.plant_id === ids[4] && r.ts >= ts[n - 12])
    for (const r of rows) r.pct = rows[0].pct
  }
  if (ids.length >= 2) {                                   // verify-fail demo
    pump.push({ ts: ts[n - 40], node: 'dummy', plant_id: ids[1], treat: pots[1][1], dur_ms: 3000, soil_before: 37.8, soil_after: 38.0, raw_before: null, raw_after: null, shots: 6, reason: 'verify fail' })
  }
  pump.sort((a, b) => b.ts - a.ts)

  const grow: GrowRow[] = []
  const d0 = localParts(t0, cfg.tz)
  const phases: ['dawn' | 'pm', number][] = [['dawn', 6], ['pm', 15]]
  for (let d = 0; d < days; d++) {
    pots.forEach(([pid, tr], k) => {
      let base = tr === 'stable' ? 11.5 * Math.exp(0.145 * d) : 11.3 * Math.exp(0.131 * d)
      base *= 1 + rng.normal(0, 0.05)
      const droop = tr === 'stable' ? rng.uniform(2, 5) : rng.uniform(9, 17)
      for (const [phase, hour] of phases) {
        const area = base * (phase === 'dawn' ? 1 : 1 - droop / 100)
        grow.push({ ts: zonedToUtc(d0.y, d0.m, d0.d + d, hour, 0, cfg.tz), plant_id: pid, treat: tr, phase, area_cm2: r2(area), area_px: Math.floor(area * 900), px_per_cm: 30, img_file: '', ok: 1, contour: blob(30 * Math.sqrt(area / 11.5), k * 13 + 3) })
      }
    })
  }

  const env: EnvRow[] = []
  const perDay = (24 * 60) / stepMin
  for (let i = 0; i < n; i++) {
    const day = hours[i] >= 7 && hours[i] < 19
    const temp = 21 + 4 * Math.sin((i / perDay) * 2 * Math.PI) + rng.normal(0, 0.2)
    const hum = Math.min(90, Math.max(35, 60 - (temp - 21) * 2.5 + rng.normal(0, 1)))
    const svp = 0.6108 * Math.exp((17.27 * temp) / (temp + 237.3))
    env.push({ ts: ts[i], node: 'dummy', temp: r2(temp), hum: r1(hum), press: r1(1013 + rng.normal(0, 0.5)), vpd: Math.round(svp * (1 - hum / 100) * 1000) / 1000, lux: Math.round(day ? 8000 + rng.normal(0, 300) : 20), co2: Math.round((day ? 520 : 640) + rng.normal(0, 15)), n: 30 })
  }
  return { soil, pump, grow, env, ts }
}
