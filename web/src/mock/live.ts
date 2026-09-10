/* WS stand-in: periodic env / soil / pump events and the capture job state machine (capture/runner.py). */
import { ApiError } from '@/api/client'
import type { Job, LiveEvent, LiveType } from '@/api/types'
import { newJob, STEP_NAMES } from './fixtures/jobs'
import { addEvent, getState, roster, type MockState } from './state'
import { bandPct, blob, Rng } from './synth'
import { iso, localDay, localParts } from './time'

let emitFn: ((ev: LiveEvent) => void) | null = null
const rng = new Rng(99)

export function broadcast(type: LiveType, data: unknown): void {
  emitFn?.({ type, ts: iso(Date.now()), data })
}

export function startLive(emit: (ev: LiveEvent) => void): void {
  if (emitFn) return
  emitFn = emit
  const st = getState()
  broadcast('hello', { mock: true, scenario: st.scenario })
  window.setInterval(() => tickEnv(getState()), 30_000)
  window.setInterval(() => tickSoil(getState()), 20_000)
}

function tickEnv(st: MockState): void {
  const env = st.frames.env
  if (!env.length || st.frames.fake.includes('env')) return
  const last = env[env.length - 1], now = Date.now()
  const temp = Number(((last.temp ?? 21) + rng.normal(0, 0.15)).toFixed(2))
  const hum = Number(Math.min(90, Math.max(35, (last.hum ?? 60) + rng.normal(0, 0.6))).toFixed(1))
  const svp = 0.6108 * Math.exp((17.27 * temp) / (temp + 237.3))
  const h = localParts(now, st.cfg.tz).h, day = h >= 7 && h < 19
  const row = { ts: now, node: last.node, temp, hum, press: last.press, vpd: Number((svp * (1 - hum / 100)).toFixed(3)), lux: day ? Math.round(8000 + rng.normal(0, 300)) : 20, co2: Math.round((day ? 520 : 640) + rng.normal(0, 15)), n: 30 }
  env.push(row)
  st.frames.now = now
  st.mqttMessages++
  broadcast('env', { row: { ...row, ts: iso(now) } })
}

let soilIdx = 0
function tickSoil(st: MockState): void {
  const fr = st.frames
  if (fr.fake.includes('soil')) return
  const r = roster(st)
  if (!r.pots.length) return
  const pid = r.pots[soilIdx++ % r.pots.length]
  const prev = [...fr.soil].reverse().find((x) => x.plant_id === pid)
  if (!prev) return
  const treat = r.treat[pid], [on, off] = bandPct(st.cfg)[treat] ?? [30, 55]
  const now = Date.now()
  let pct = Number(((prev.pct ?? off) - 0.35 + rng.normal(0, 0.2)).toFixed(2))
  if (pct <= on) {
    const pump = { ts: now, node: prev.node, plant_id: pid, treat, dur_ms: Math.round(rng.uniform(2400, 3600)), soil_before: pct, soil_after: off, raw_before: null, raw_after: null, shots: 1, reason: 'filled' }
    fr.pump.unshift(pump)
    pct = off
    st.mqttMessages++
    broadcast('pump', { row: { ...pump, ts: iso(now) }, retained: false })
  }
  const row = { ...prev, ts: now, pct }
  fr.soil.push(row)
  fr.now = now
  st.mqttMessages++
  broadcast('soil', { row: { ...row, ts: iso(now) } })
}

// ---- capture job -----------------------------------------------------------------
const WAIT: Record<string, number> = { lock: 150, led_on: 100, camera_open: 200, controls: 300, settle: 200, capture: 500, led_off: 2000, measure: 100, jsonl: 3000, publish: 100, done: 1000 }
let cancelFlag = false
let lastMarkMs = 0

function mark(job: Job, step: string): void {
  const now = Date.now()
  const prev = job.steps[job.steps.length - 1]
  if (prev) prev.ms = now - lastMarkMs
  lastMarkMs = now
  job.steps.push({ name: step, at: iso(now), ms: null })
  job.step = step
  broadcast('capture.progress', structuredClone(job))
}

export function startJob(st: MockState, phase: string): Job {
  if (st.job) throw new ApiError(409, 'job_running', 'a capture job is already running')
  if (!['auto', 'dawn', 'pm'].includes(phase)) throw new ApiError(400, 'bad_phase', 'phase must be auto|dawn|pm')
  const now = Date.now(), lp = localParts(now, st.cfg.tz)
  const ph = phase === 'dawn' || phase === 'pm' ? phase : lp.h < 12 ? 'dawn' : 'pm'
  const job = newJob(ph, 'api', now, `${localDay(now, st.cfg.tz)}_${String(lp.h).padStart(2, '0')}${String(lp.mi).padStart(2, '0')}.jpg`)
  st.job = job
  cancelFlag = false
  Object.assign(st.cam, { preview: 'paused_capture', pausedFor: 'capture', opsBusy: 'job', state: 'open' })
  mark(job, 'queued')
  job.state = 'running'
  broadcast('camera.state', { state: 'open', preview: 'paused_capture' })
  const steps = [...STEP_NAMES.slice(1), 'done']
  const next = (i: number) => {
    window.setTimeout(() => {
      if (cancelFlag) return finish(st, job, 'cancelled', 'cancelled by user')
      const name = steps[i]
      if (name === 'led_on') job.log.push('[LED] skipped — LED not installed (led.enabled=false)')
      if (name === 'led_off') job.log.push(`[${job.img_file}] shot ${job.img_file}`)
      if (name === 'jsonl') measure(st, job)
      if (name === 'publish') { job.published = true; job.log.push(`[${job.img_file}] ${job.phase}  ${job.ok_rows}/${job.n_rows} ok  ->  ${st.cfg.mqtt.growth_topic} 발행`) }
      if (name === 'done') return finish(st, job, job.ok_rows ? 'done' : 'failed', job.ok_rows ? null : 'no valid measurement — check photos/debug')
      mark(job, name)
      next(i + 1)
    }, WAIT[steps[i]])
  }
  next(0)
  return structuredClone(job)
}

function measure(st: MockState, job: Job): void {
  const fr = st.frames
  job.rows = st.cfg.rois.map((roi) => {
    const last = [...fr.grow].sort((a, b) => b.ts - a.ts).find((r) => r.plant_id === roi.plant_id && r.phase === 'dawn')
    const base = last?.area_cm2 ?? 11.5 * Math.exp(0.145 * 7)
    const area = Number((base * (1 + rng.uniform(0.005, 0.04)) * (job.phase === 'pm' ? 1 - rng.uniform(0.02, 0.12) : 1)).toFixed(2))
    return { plant_id: roi.plant_id, treat: roi.treat || null, area_cm2: area, ok: 1 }
  })
  job.n_rows = job.rows.length
  job.ok_rows = job.rows.length
  for (const r of job.rows) job.log.push(`  ${r.plant_id.padStart(4)} ${String(r.area_cm2).padStart(8)} cm2  ok  contour`)
}

function finish(st: MockState, job: Job, state: Job['state'], error: string | null): void {
  job.state = state
  job.error = error
  job.finished_at = iso(Date.now())
  mark(job, state)
  st.job = null
  st.jobs.unshift(job)
  Object.assign(st.cam, { preview: 'live', pausedFor: null, opsBusy: null, state: 'closed' })
  addEvent(st, `capture.${state}`, { id: job.id, phase: job.phase, trigger: job.trigger, ok_rows: job.ok_rows, n_rows: job.n_rows, img_file: job.img_file, error })
  broadcast('capture.done', structuredClone(job))
  broadcast('camera.state', { state: 'closed', preview: 'live' })
  if (state !== 'done') return
  const now = Date.now()
  job.rows.forEach((r, k) => {
    const area = r.area_cm2 ?? 0
    st.frames.grow.push({ ts: now, plant_id: r.plant_id, treat: r.treat, phase: job.phase as 'dawn' | 'pm', area_cm2: area, area_px: Math.floor(area * 900), px_per_cm: st.cfg.qc.px_per_cm_ref, img_file: job.img_file ?? '', ok: 1, contour: blob(30 * Math.sqrt(area / 11.5), k * 13 + 3) })
  })
  st.frames.now = now
  st.mqttMessages++
  broadcast('growth', { t: iso(now), phase: job.phase, img: job.img_file, plants: job.rows })
}

export function cancelJob(st: MockState): boolean {
  if (!st.job) return false
  cancelFlag = true
  return true
}
