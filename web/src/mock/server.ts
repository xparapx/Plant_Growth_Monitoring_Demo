/* In-process mock of the plantsvc REST API.  `handle(path, init)` resolves the typed shape for every endpoint the app uses. */
import type { FetchInit } from '@/api/client'
import { ApiError } from '@/api/client'
import type { ConfigDoc, ImageFile, ImagesList, LiveEvent, PlantConfig } from '@/api/types'
import { runAction } from './cameraActions'
import { checkConfig, deepMerge, validateConfig } from './fixtures/config'
import { systemStatus } from './fixtures/system'
import { cancelJob, startJob, startLive as liveStart, broadcast } from './live'
import { MOCK_PREVIEW_SRC } from './preview'
import { analytics, envSeries, exportCsv, growthRows, health, pumpRecentDoc, soilSeries, summary } from './serverData'
import { addEvent, bumpConfig, cameraStatus, captureStatus, configDoc, getState, latestRaw, ledStatus, type MockState } from './state'
import { iso, localDay } from './time'

const LATENCY_MS = 150
const sleep = (ms: number) => new Promise<void>((r) => window.setTimeout(r, ms))

export async function handle<T>(path: string, init: FetchInit = {}): Promise<T> {
  await sleep(LATENCY_MS)
  const st = getState()
  const u = new URL(path, 'http://mock.local')
  const out = route(st, u.pathname, u.searchParams, init.method ?? 'GET', init)
  if (out === undefined) throw new ApiError(404, 'not_found', path)
  return out as T
}

export function startLive(emit: (ev: LiveEvent) => void): void {
  liveStart(emit)
}

function route(st: MockState, p: string, q: URLSearchParams, method: string, init: FetchInit): unknown {
  const int = (k: string, d: number) => { const v = Number(q.get(k)); return Number.isFinite(v) && q.has(k) ? v : d }
  let m: RegExpMatchArray | null

  // ---- dashboard ----------------------------------------------------------------
  if (p === '/api/summary') return summary(st)
  if (p === '/api/health') return health(st)
  if (p === '/api/env') return envSeries(st, q)
  if (p === '/api/soil') return soilSeries(st, q)
  if (p === '/api/pump/recent') return pumpRecentDoc(st, int('n', 5))
  if (p === '/api/growth') return growthRows(st, q)
  if ((m = p.match(/^\/api\/analytics\/([\w-]+)$/))) return analytics(st, m[1])
  if ((m = p.match(/^\/api\/export\/(\w+)\.csv$/))) return exportCsv(st, m[1])

  // ---- camera ---------------------------------------------------------------------
  if (p === '/api/camera/status') return cameraStatus(st)
  if ((m = p.match(/^\/api\/camera\/actions\/(\w+)$/)) && method === 'POST') return runAction(st, m[1], (init.body ?? {}) as Record<string, unknown>)
  if (p === '/api/camera/drift') return drift(st)
  if (p === '/api/camera/calib.jpg' || p === '/api/camera/frame.jpg' || p === '/api/camera/stream.mjpg') return null
  if (p === '/api/camera/calib/info') return st.calibExists ? { exists: true, size: 1_843_200, mtime: st.calibMtime } : { exists: false }
  if (p === '/api/images') return images(st, q.get('kind') ?? 'raw', int('limit', 50))

  // ---- capture / led / events ----------------------------------------------------------
  if (p === '/api/capture/status') return captureStatus(st)
  if (p === '/api/capture/schedule') return captureStatus(st).schedule
  if (p === '/api/capture/run' && method === 'POST') return { job: startJob(st, q.get('phase') ?? 'auto') }
  if (p === '/api/capture/cancel' && method === 'POST') return { cancelled: cancelJob(st) }
  if (p === '/api/capture/current') return { job: st.job }
  if (p === '/api/capture/jobs') return { jobs: st.jobs.slice(0, int('limit', 20)) }
  if ((m = p.match(/^\/api\/capture\/jobs\/(\w+)$/))) { const j = st.jobs.find((x) => x.id === m![1]); if (!j) throw new ApiError(404, 'no_job', m[1]); return j }
  if (p === '/api/capture/replay' && method === 'POST') return replay(st)
  if (p === '/api/led') return ledStatus(st)
  if (p === '/api/led/on' || p === '/api/led/test') throw new ApiError(409, 'led_not_installed', 'LED not installed (led.enabled=false)')
  if (p === '/api/led/off') return ledStatus(st)
  if (p === '/api/events') {
    const type = q.get('type')
    return { events: st.events.filter((e) => !type || e.type === type).slice(0, int('limit', 100)), now: iso(Date.now()) }
  }

  // ---- config ------------------------------------------------------------------------
  if (p === '/api/config') {
    if (method === 'GET') return configDoc(st)
    if (method === 'PATCH' || method === 'PUT') return writeConfig(st, init, method === 'PATCH')
  }
  if (p === '/api/config/check') return checkConfig(st.cfg)
  if (p === '/api/config/db-check') return dbCheck(st)

  // ---- system ------------------------------------------------------------------------
  if (p === '/api/system/status') return systemStatus(st)
  if (p === '/api/system/logs') return { unit: q.get('unit') ?? 'plantsvc', lines: [], available: false }
  if (p === '/api/system/time') return { time: iso(Date.now()), epoch: Date.now() / 1000 }
  return undefined
}

function writeConfig(st: MockState, init: FetchInit, patch: boolean): ConfigDoc {
  const ifMatch = init.headers?.['If-Match'] ?? init.headers?.['if-match']
  if (ifMatch && String(st.mtime) !== ifMatch) throw new ApiError(409, 'stale', 'config changed since you loaded it — reload and retry')
  const body = (init.body ?? {}) as Record<string, unknown>
  const next = patch ? deepMerge(structuredClone(st.cfg), body) : (body as unknown as PlantConfig)
  const err = validateConfig(next)
  if (err) throw new ApiError(422, 'invalid_config', err)
  bumpConfig(st, () => next)
  addEvent(st, 'config.changed', { keys: Object.keys(body) })
  broadcast('config.changed', { keys: Object.keys(body) })
  return configDoc(st)
}

function drift(st: MockState) {
  if (!st.calibExists) return { level: 'unknown', msg: 'calib.jpg 가 없습니다', ok: false, cur: null }
  const cur = latestRaw(st)
  if (!cur) return { level: 'unknown', msg: '촬영된 사진이 아직 없습니다', ok: false, cur: null }
  const ppc = st.cfg.qc.px_per_cm_ref
  return { ok: true, dx: 1.2, dy: -0.8, mag: 1.4, resp: 0.31, deg: 0.04, scale: 1.001, resp_rs: 0.29, level: 'ok', msg: '기준 사진과 1.4 px 차이 — 정상', cur, mag_mm: ppc ? Math.round((1.4 / ppc) * 1000) / 100 : null }
}

function images(st: MockState, kind: string, limit: number): ImagesList {
  const file = (name: string, mtime: number, fake = false): ImageFile => {
    const m = name.match(/^(fake_)?(\d{4}-\d{2}-\d{2}_\d{4})(?:_(p\d+))?\./)
    return { name, size: 1_640_000 + (name.length * 7919) % 90_000, mtime, stem: m?.[2] ?? null, plant_id: m?.[3] ?? null, fake: fake || Boolean(m?.[1]), url: MOCK_PREVIEW_SRC }
  }
  const stems = [...new Set([...st.frames.grow.map((r) => r.img_file), ...st.jobs.filter((j) => j.state === 'done').map((j) => j.img_file ?? '')].filter(Boolean))].sort().reverse()
  const mt = (name: string) => { const r = st.frames.grow.find((g) => g.img_file === name); return Math.floor((r?.ts ?? Date.now()) / 1000) }
  let files: ImageFile[] = []
  if (kind === 'raw') files = stems.map((n) => file(n, mt(n)))
  else if (kind === 'debug' || kind === 'mask') files = stems.flatMap((n) => st.cfg.rois.map((r) => file(n.replace(/\.jpg$/, `_${r.plant_id}.${kind === 'mask' ? 'png' : 'jpg'}`), mt(n))))
  else if (kind === 'calib') files = st.calibExists ? [file('calib.jpg', st.calibMtime ?? 0)] : []
  else if (kind === 'data') files = st.calibExists && st.cfg.rois.length ? [file('roi_offset.jpg', Math.floor(Date.now() / 1000))] : []
  else throw new ApiError(404, 'bad_kind', 'kind must be one of raw, debug, mask, calib, data')
  return { kind, files: files.slice(0, limit) }
}

function replay(st: MockState) {
  const done = st.jobs.filter((j) => j.state === 'done')
  const unpublished = done.filter((j) => !j.published)
  unpublished.forEach((j) => { j.published = true; j.publish_error = null })
  const last = st.frames.grow.length ? Math.max(...st.frames.grow.map((r) => r.ts)) : Date.now()
  addEvent(st, 'capture.replay', { sent: unpublished.length, skipped: done.length - unpublished.length })
  return { last_db_ts: iso(last), sent: unpublished.length, skipped: done.length - unpublished.length, errors: [] as string[] }
}

function dbCheck(st: MockState) {
  const want = Object.fromEntries(st.cfg.rois.map((r) => [r.plant_id, r.treat]))
  const tables: Record<string, unknown[]> = {}
  let mismatched = 0
  for (const [t, rows] of [['soil', st.frames.soil], ['pump_log', st.frames.pump], ['growth', st.frames.grow]] as const) {
    const grp = new Map<string, { plant_id: string; treat: string | null; rows: number; min_ts: number; max_ts: number }>()
    for (const r of rows) {
      const k = `${r.plant_id}|${r.treat ?? ''}`
      const g = grp.get(k) ?? { plant_id: r.plant_id, treat: r.treat, rows: 0, min_ts: r.ts, max_ts: r.ts }
      g.rows++; g.min_ts = Math.min(g.min_ts, r.ts); g.max_ts = Math.max(g.max_ts, r.ts)
      grp.set(k, g)
    }
    tables[t] = [...grp.values()].sort((a, b) => a.plant_id.localeCompare(b.plant_id)).map((g) => {
      const ok = (want[g.plant_id] ?? '\0') === (g.treat ?? '')
      if (!ok) mismatched += g.rows
      return { ...g, min_ts: localDay(g.min_ts, 'UTC') , max_ts: iso(g.max_ts), ok, config_treat: want[g.plant_id] ?? null }
    })
  }
  return { want, tables, mismatched_rows: mismatched }
}
