/* Data endpoints of the mock: summary / health / env / soil / growth / pump / analytics / export. */
import { ApiError } from '@/api/client'
import type { EnvKey, EnvSeries, PumpRecent, SoilSeries, Summary, TableName } from '@/api/types'
import { ENV_KEYS } from '@/api/types'
import { alignmentTrend, envSummary, histogram, nodesAndAlerts, reference, validity } from './analytics'
import { meta, suggestedSql, type Frames } from './frames'
import { canopySeries, droop, droopTimeline, pumpRecent, rgr, silhouettes, waterSummary } from './growth'
import { ledStatus, roster, type MockState } from './state'
import { bucketSeconds, iso, resample, round } from './time'
import { bandPct } from './synth'

const conflictsOf = (r: ReturnType<typeof roster>) => Object.entries(r.conflicts).sort().map(([pot, sources]) => ({ pot, sources }))

export function summary(st: MockState): Summary {
  const fr = st.frames, r = roster(st)
  const { nodes, alerts } = nodesAndAlerts(fr, r, st.cfg)
  const src = (t: TableName, n: number) => (fr.fake.includes(t) ? 'dummy' : n ? 'real' : 'none')
  return {
    ...meta(fr), sources: { env: src('env', fr.env.length), soil: src('soil', fr.soil.length), pump: src('pump', fr.pump.length), growth: src('growth', fr.grow.length) },
    pots: r.pots.map((p) => ({ id: p, treat: r.treat[p] ?? null, real: fr.real_pots.has(p) })), groups: r.groups, ncol: r.ncol,
    conflicts: conflictsOf(r), unknown_labels: r.unknown, suggested_sql: suggestedSql(r),
    env: envSummary(fr), nodes, alerts, validity: validity(fr, r, st.cfg),
    run_started: st.cfg.run_started, tz: st.cfg.tz, real_env: fr.real_env, capture: { driver: 'mock' }, led: ledStatus(st),
  }
}

export function health(st: MockState) {
  const fr = st.frames, r = roster(st)
  const { nodes, alerts } = nodesAndAlerts(fr, r, st.cfg)
  return {
    ...meta(fr), pots: r.pots.map((p) => ({ id: p, treat: r.treat[p] ?? null, real: fr.real_pots.has(p), sources: r.sources[p] ?? {} })),
    groups: r.groups, unknown_labels: r.unknown, suggested_sql: suggestedSql(r), conflicts: conflictsOf(r), nodes, alerts,
    sensors: Object.fromEntries(ENV_KEYS.map((k) => [k, { missing: envSummary(fr, 0)[k].missing }])), real_env: fr.real_env,
  }
}

function window<T extends { ts: number }>(rows: T[], q: URLSearchParams): { rows: T[]; a: number | null; b: number | null } {
  const parse = (s: string | null) => (s ? new Date(s).getTime() : NaN)
  let a = parse(q.get('from')), b = parse(q.get('to'))
  let out = rows
  if (!Number.isNaN(a)) out = out.filter((r) => r.ts >= a)
  if (!Number.isNaN(b)) out = out.filter((r) => r.ts < b)
  if (Number.isNaN(a)) a = out.length ? Math.min(...out.map((r) => r.ts)) : NaN
  if (Number.isNaN(b)) b = out.length ? Math.max(...out.map((r) => r.ts)) : NaN
  return { rows: out, a: Number.isNaN(a) ? null : a, b: Number.isNaN(b) ? null : b }
}

function bucket(q: URLSearchParams, a: number | null, b: number | null): number {
  try { return bucketSeconds(q.get('bucket') ?? 'auto', a, b, Number(q.get('points') ?? 600)) } catch { throw new ApiError(400, 'bad_bucket', 'bucket must be one of raw,5m,15m,1h,6h,1d or auto') }
}

export function envSeries(st: MockState, q: URLSearchParams): EnvSeries {
  const fr = st.frames
  const { rows, a, b } = window(fr.env, q)
  const bs = bucket(q, a, b)
  const cols = ['temp', 'hum', 'press', 'vpd', 'lux', 'co2'] as const
  const r = resample(rows, [...cols], bs)
  const series: EnvSeries['series'] = { ts: r.map((x) => iso(x.ts)) }
  for (const c of cols) series[c] = r.map((x) => (x.vals[c] === null ? null : round(x.vals[c]!, 3)))
  if (r.length) series.n = r.map((x) => x.n)
  const s = envSummary(fr, 0)
  const pick = <K extends keyof (typeof s)[EnvKey]>(k: K) => Object.fromEntries(ENV_KEYS.map((e) => [e, s[e][k]])) as Record<EnvKey, (typeof s)[EnvKey][K]>
  return { ...meta(fr), bucket: bs, series, current: pick('value'), delta_24h: pick('delta_1d'), missing: pick('missing') }
}

export function soilSeries(st: MockState, q: URLSearchParams): SoilSeries {
  const fr = st.frames, r = roster(st)
  const { rows, a, b } = window(fr.soil, q)
  const bs = bucket(q, a, b)
  const band = bandPct(st.cfg)
  const pcts = fr.soil.map((x) => x.pct).filter((x): x is number => x !== null)
  let lo = Math.min(pcts.length ? Math.min(...pcts) : Infinity, ...Object.values(band).map((x) => x[0]))
  let hi = Math.max(pcts.length ? Math.max(...pcts) : -Infinity, ...Object.values(band).map((x) => x[1]))
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) { lo = 20; hi = 85 }
  const pad = Math.max(2, (hi - lo) * 0.06)
  const want = q.get('pots')?.split(',').map((p) => p.trim()).filter(Boolean) ?? r.pots
  const pots: SoilSeries['pots'] = []
  for (const p of want) {
    const s = rows.filter((x) => x.plant_id === p)
    if (!s.length) continue
    const rs = resample(s, ['pct'], bs)
    pots.push({ plant_id: p, treat: r.treat[p] ?? null, ts: rs.map((x) => iso(x.ts)), pct: rs.map((x) => (x.vals.pct === null ? null : round(x.vals.pct!, 2))), n: rs.map((x) => x.n) })
  }
  return {
    ...meta(fr), bucket: bs, groups: r.groups, basis: q.get('basis') ?? 'pct',
    band_pct: Object.fromEntries(Object.entries(band).map(([k, [x, y]]) => [k, [round(x, 2), round(y, 2)]])) as Record<string, [number, number]>,
    yrange: [round(Math.max(0, lo - pad), 2), round(Math.min(100, hi + pad), 2)], pots,
  }
}

export function growthRows(st: MockState, q: URLSearchParams) {
  const fr = st.frames
  let rows = window(fr.grow, q).rows
  const phase = q.get('phase'), pots = q.get('pots')
  if (phase === 'dawn' || phase === 'pm') rows = rows.filter((r) => r.phase === phase)
  if (pots) { const w = pots.split(',').map((p) => p.trim()); rows = rows.filter((r) => w.includes(r.plant_id)) }
  const contour = q.get('contour') === '1'
  return { ...meta(fr), rows: rows.map((r) => ({ ...r, ts: iso(r.ts), contour: contour ? r.contour : undefined })) }
}

export const pumpRecentDoc = (st: MockState, n: number): PumpRecent => ({ ...meta(st.frames), ...pumpRecent(st.frames, roster(st), n) })

export function analytics(st: MockState, name: string): unknown {
  const fr = st.frames, r = roster(st), cfg = st.cfg, m = meta(fr)
  switch (name) {
    case 'validity': return { ...m, ...validity(fr, r, cfg) }
    case 'histogram': return { ...m, ...histogram(fr, r, cfg) }
    case 'alignment-trend': return { ...m, ...alignmentTrend(fr, r, cfg) }
    case 'reference': return { ...m, ...reference(fr) }
    case 'droop': return { ...m, ...droop(fr, r, cfg) }
    case 'droop-timeline': return { ...m, ...droopTimeline(fr, r, cfg) }
    case 'canopy': return { ...m, ...canopySeries(fr, r) }
    case 'silhouettes': return { ...m, ...silhouettes(fr, r) }
    case 'rgr': return { ...m, ...rgr(fr, r) }
    case 'water': return { ...m, ...waterSummary(fr, r, cfg.tz) }
    case 'all': {
      const { nodes, alerts } = nodesAndAlerts(fr, r, cfg)
      return {
        ...m, groups: r.groups, pots: r.pots, health: { nodes, alerts, conflicts: r.conflicts, unknown: r.unknown }, env: envSummary(fr),
        validity: validity(fr, r, cfg), histogram: histogram(fr, r, cfg), alignment: alignmentTrend(fr, r, cfg), reference: reference(fr),
        droop: droop(fr, r, cfg), droop_timeline: droopTimeline(fr, r, cfg), canopy: canopySeries(fr, r), silhouettes: silhouettes(fr, r),
        rgr: rgr(fr, r), pump_recent: pumpRecent(fr, r), water: waterSummary(fr, r, cfg.tz),
      }
    }
    default: return undefined
  }
}

const TABLE: Record<string, keyof Pick<Frames, 'env' | 'soil' | 'pump' | 'grow'>> = { readings: 'env', soil: 'soil', pump_log: 'pump', growth: 'grow' }

export function exportCsv(st: MockState, table: string): string {
  const key = TABLE[table]
  if (!key) throw new ApiError(404, 'bad_table', `table must be one of ${Object.keys(TABLE).join(', ')}`)
  const rows = st.frames[key] as unknown as Record<string, unknown>[]
  if (!rows.length) return ''
  const cols = Object.keys(rows[0]).filter((c) => c !== 'contour')
  const cell = (v: unknown) => (v === null || v === undefined ? '' : typeof v === 'string' ? (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v) : String(v))
  const fmtTs = (ms: number) => iso(ms).replace('T', ' ').replace('Z', '')
  return [cols.join(','), ...rows.map((r) => cols.map((c) => (c === 'ts' ? fmtTs(r.ts as number) : cell(r[c]))).join(','))].join('\n') + '\n'
}
