/* TS ports of analytics/soil.py and analytics/health.py (validity, histogram, alignment, env summary, nodes/alerts). */
import type { Alert, EnvKey, EnvStat, NodeHealth, PlantConfig, Validity } from '@/api/types'
import { ENV_KEYS } from '@/api/types'
import type { EnvRow, Frames, Roster } from './frames'
import { suggestedSql } from './frames'
import { iso, isoWeek, localDay, round } from './time'

export const mean = (v: number[]) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : NaN)
export function sd(v: number[]): number {
  if (v.length < 2) return NaN
  const m = mean(v)
  return Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / (v.length - 1))
}
/** pandas quantile (linear interpolation). */
export function quantile(v: number[], q: number): number {
  const s = [...v].sort((a, b) => a - b)
  const pos = (s.length - 1) * q, lo = Math.floor(pos), hi = Math.ceil(pos)
  return s[lo] + (s[hi] - s[lo]) * (pos - lo)
}

function groupPct(fr: Frames, roster: Roster): Record<string, number[]> {
  const out: Record<string, number[]> = {}
  for (const r of fr.soil) {
    const g = roster.treat[r.plant_id]
    if (g === undefined || r.pct === null) continue
    ;(out[g] ??= []).push(r.pct)
  }
  return out
}

export function validity(fr: Frames, roster: Roster, cfg: PlantConfig): Validity {
  const tol = cfg.analysis.tol_pp, sep = cfg.analysis.sep_ratio
  const out: Validity = { tol_pp: tol, sep_ratio: sep, enough_groups: false, groups: roster.groups, mu: {}, sd: {}, n: {}, dmu: null, aligned: null, ratio: null, separated: null }
  const g = groupPct(fr, roster)
  for (const [k, v] of Object.entries(g)) {
    out.mu[k] = round(mean(v), 3); out.n[k] = v.length
    const s = sd(v); if (!Number.isNaN(s)) out.sd[k] = round(s, 3)
  }
  if ('stable' in out.mu && 'fluct' in out.mu && out.sd.stable > 0) {
    const dmu = Math.abs(out.mu.stable - out.mu.fluct), ratio = out.sd.fluct / out.sd.stable
    Object.assign(out, { enough_groups: true, dmu: round(dmu, 3), aligned: dmu <= tol, ratio: round(ratio, 3), separated: ratio >= sep })
  }
  return out
}

export function histogram(fr: Frames, roster: Roster, cfg: PlantConfig) {
  const bins = cfg.analysis.hist_bins
  const out = { edges: [] as number[], groups: {} as Record<string, { prob: number[]; mu: number; sd: number; n: number }>, e_w: null as number | null, quantiles: { p05: null as number | null, p95: null as number | null, mean: null as number | null } }
  const g = groupPct(fr, roster)
  const vals = Object.values(g).flat()
  if (!vals.length) return out
  const lo = Math.min(...vals)
  let hi = Math.max(...vals)
  if (hi <= lo) hi = lo + 1
  const edges = Array.from({ length: bins + 1 }, (_, i) => lo + ((hi - lo) * i) / bins)
  out.edges = edges.map((e) => round(e, 3))
  const mus: number[] = []
  for (const k of Object.keys(roster.groups)) {
    const v = g[k]
    if (!v?.length) continue
    const cnt = new Array<number>(bins).fill(0)
    for (const x of v) {
      let i = Math.floor(((x - lo) / (hi - lo)) * bins)
      if (i >= bins) i = bins - 1
      cnt[i]++
    }
    out.groups[k] = { prob: cnt.map((c) => round(c / Math.max(1, v.length), 5)), mu: round(mean(v), 3), sd: round(sd(v), 3), n: v.length }
    mus.push(mean(v))
  }
  if (mus.length === 2) out.e_w = round(mean(mus), 3)
  out.quantiles = { p05: round(quantile(vals, 0.05), 3), p95: round(quantile(vals, 0.95), 3), mean: round(mean(vals), 3) }
  return out
}

export function alignmentTrend(fr: Frames, roster: Roster, cfg: PlantConfig) {
  const tbl = new Map<string, Record<string, number[]>>()
  for (const r of fr.soil) {
    const g = roster.treat[r.plant_id]
    if (g === undefined || r.pct === null) continue
    const wk = isoWeek(localDay(r.ts, cfg.tz))
    let row = tbl.get(wk)
    if (!row) { row = {}; tbl.set(wk, row) }
    ;(row[g] ??= []).push(r.pct)
  }
  const weeks = [...tbl.keys()].sort()
  const groups: Record<string, (number | null)[]> = {}
  for (const k of Object.keys(roster.groups)) {
    if (!weeks.some((w) => tbl.get(w)![k])) continue
    groups[k] = weeks.map((w) => { const v = tbl.get(w)![k]; return v ? round(mean(v), 3) : null })
  }
  return { weeks, groups }
}

export function reference(fr: Frames) {
  const v = fr.soil.map((r) => r.pct).filter((x): x is number => x !== null)
  if (!v.length) return { p05: null, p95: null, mean: null }
  return { p05: round(quantile(v, 0.05), 3), p95: round(quantile(v, 0.95), 3), mean: round(mean(v), 3) }
}

// ---- health.py ----------------------------------------------------------------
const BME: string[] = ['temp', 'hum', 'press', 'vpd']
export const ENV_META: Record<EnvKey, { label: string; unit: string; digits: number }> = {
  vpd: { label: 'VPD', unit: 'kPa', digits: 2 }, temp: { label: 'Temp', unit: '°C', digits: 1 }, hum: { label: 'RH', unit: '%', digits: 0 },
  co2: { label: 'CO₂', unit: 'ppm', digits: 0 }, lux: { label: 'Light', unit: 'lx', digits: 0 },
}
const col = (r: EnvRow, k: string) => (r as unknown as Record<string, number | null>)[k] ?? null

export function envMissing(env: EnvRow[], key: string): boolean {
  if (!env.length) return true
  const tail = env.slice(-12)
  if (tail.every((r) => col(r, key) === null)) return true
  if (BME.includes(key) && tail.every((r) => Math.abs(col(r, 'temp') ?? 0) < 0.05 && Math.abs(col(r, 'hum') ?? 0) < 0.05)) return true
  return false
}

export function envSummary(fr: Frames, sparkPoints = 288): Record<EnvKey, EnvStat> {
  const env = fr.env
  const out = {} as Record<EnvKey, EnvStat>
  if (!env.length) {
    for (const k of ENV_KEYS) out[k] = { ...ENV_META[k], value: null, delta_1d: null, missing: true, spark: [] }
    return out
  }
  const cur = env[env.length - 1], day = env[Math.max(0, env.length - 288)]
  for (const k of ENV_KEYS) {
    const miss = envMissing(env, k)
    const spark = sparkPoints ? env.slice(-sparkPoints).map((r) => { const v = col(r, k); return v === null ? null : round(v, 3) }) : []
    const val = miss ? null : col(cur, k)
    const dv = col(day, k)
    const delta = !miss && k !== 'lux' && dv !== null && val !== null ? val - dv : null
    out[k] = { ...ENV_META[k], value: val, delta_1d: delta, missing: miss, spark: miss ? [] : spark }
  }
  return out
}

const minutesAgo = (now: number | null, ts: number | null) => (now === null || ts === null ? null : Math.floor((now - ts) / 60000))
const last = (rows: { ts: number }[]) => (rows.length ? Math.max(...rows.map((r) => r.ts)) : null)

export function nodesAndAlerts(fr: Frames, roster: Roster, cfg: PlantConfig): { nodes: NodeHealth[]; alerts: Alert[] } {
  const nodes: NodeHealth[] = [], alerts: Alert[] = []
  const chip = (name: string, kind: NodeHealth['kind'], mins: number | null, every: number, real: boolean, stuck = false, pot: string | null = null, lastTs: number | null = null) => {
    let state: NodeHealth['state'] = 'off'
    if (real) state = stuck || mins === null || mins > every * 12 ? 'bad' : mins > every * 4 ? 'amber' : 'ok'
    nodes.push({ name, kind, pot, real, state, minutes_ago: mins, every_min: every, stuck, last_ts: lastTs === null ? null : iso(lastTs) })
  }
  const envLast = last(fr.env)
  chip('ENV', 'env', minutesAgo(fr.now, envLast), cfg.analysis.env_interval_min, fr.real_env, false, null, envLast)
  for (const p of roster.pots) {
    const real = fr.real_pots.has(p)
    const s = fr.soil.filter((r) => r.plant_id === p)
    const tail = s.slice(-12).map((r) => r.pct)
    const stuck = real && tail.length >= 12 && new Set(tail).size === 1
    const l = last(s)
    chip(p.toUpperCase(), 'pot', minutesAgo(fr.now, l), cfg.analysis.soil_interval_min, real, stuck, p, l)
    if (stuck) alerts.push({ level: 'error', code: 'stuck_sensor', pots: [p], text: `${p.toUpperCase()} — value unchanged, node still transmitting. Irrigation is running on a dead reading. Check I2C lead.` })
  }
  const growLast = last(fr.grow)
  const camReal = !fr.fake.includes('growth') && fr.grow.length > 0
  chip('CAM', 'cam', camReal ? minutesAgo(fr.now, growLast) : null, cfg.analysis.cam_interval_min, camReal, false, null, growLast)

  const vf = [...new Set(fr.pump.filter((r) => (r.reason ?? '').replace(/_/g, ' ').trim() === 'verify fail').map((r) => r.plant_id))].filter((p) => fr.real_pots.has(p))
  if (vf.length) alerts.push({ level: 'error', code: 'verify_fail', pots: vf, text: `${vf.map((v) => v.toUpperCase()).join(', ')} — pump ran, no moisture rise. Node disarmed. Check tube and tank.` })
  const gone = ENV_KEYS.filter((k) => fr.real_env && envMissing(fr.env, k)).map((k) => ENV_META[k].label)
  if (gone.length) alerts.push({ level: 'warn', code: 'sensor_missing', keys: gone, text: `${gone.join(', ')} 가 실측이 아닙니다 — BME688 미연결이거나 읽기 실패입니다. 0 이 아니라 결측으로 기록되도록 노드 펌웨어를 고치세요.` })
  if (roster.unknown.length) alerts.push({ level: 'error', code: 'unknown_treat', labels: roster.unknown, sql: suggestedSql(roster), text: `Unrecognised treatment label(s): ${JSON.stringify(roster.unknown)}. Expected 'stable' or 'fluct'. Probably left over from an MQTT test — delete them.` })
  if (Object.keys(roster.conflicts).length) alerts.push({ level: 'error', code: 'treat_conflict', pots: Object.keys(roster.conflicts).sort(), detail: roster.conflicts, text: '처리군 불일치 — 이 화분들은 그리지 않습니다. 펌프 호스가 실제로 꽂힌 화분을 기준으로 water_node.ino 의 TREAT_FLUCT·PLANT_ID 와 config.json 의 rois[].treat 를 맞추세요. 과거 행을 지우기 전에 plant.db 를 백업하세요.' })
  return { nodes, alerts }
}
