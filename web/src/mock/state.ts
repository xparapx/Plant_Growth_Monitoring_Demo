/* Mutable in-memory state of the mock service (config store, camera session, jobs, events). */
import type { CameraStatus, CaptureStatus, ConfigDoc, EventRow, Job, LedStatus, PlantConfig, Roi, Schedule } from '@/api/types'
import { buildRoster, type Frames, type Roster } from './frames'
import { CAP, PREVIEW, SCALE, checkConfig, defaultConfig } from './fixtures/config'
import { failedJob, seedEvents } from './fixtures/jobs'
import { buildFrames, currentScenario, scenarioSetup, type Scenario } from './scenarios'
import { addMinutes, iso, nextOccurrence } from './time'

export interface SetupSession {
  msg: string; level: CameraStatus['msg_level']; pts: [number, number][]; ppcFixed: number | null; cm: number
  order: number[] | null; lastAuto: Record<string, unknown> | null
}
export interface MockState {
  scenario: Scenario; cfg: PlantConfig; mtime: number; warnings: string[]
  frames: Frames; calibExists: boolean; calibMtime: number | null
  cam: { state: CameraStatus['state']; preview: CameraStatus['preview']; pausedFor: string | null; clients: number; opsBusy: string | null }
  setup: SetupSession
  job: Job | null; jobs: Job[]; events: EventRow[]; nextEventId: number; mqttMessages: number; startedAt: number
}

let state: MockState | null = null

export function getState(): MockState {
  if (state) return state
  const scenario = currentScenario()
  const now = Date.now()
  const s = scenarioSetup(scenario, now)
  const cfg = defaultConfig({ rois: s.rois, ppc: s.ppc, treatMode: s.treatMode, lens: s.lens, runStarted: s.runStarted })
  const frames = buildFrames(scenario, cfg, now)
  state = {
    scenario, cfg, mtime: now * 1000, warnings: [], frames, calibExists: s.calib, calibMtime: s.calib ? Math.floor(now / 1000) - 6 * 86400 : null,
    cam: { state: 'closed', preview: 'live', pausedFor: null, clients: 0, opsBusy: null },
    setup: { msg: '준비됨', level: 'info', pts: [], ppcFixed: null, cm: 0, order: null, lastAuto: null },
    job: null, jobs: s.failedJob ? [failedJob(now)] : [], events: [], nextEventId: 1, mqttMessages: 0, startedAt: now - 6 * 60_000,
  }
  seedEvents(state, now)
  return state
}

export const roster = (st: MockState): Roster => buildRoster(st.frames.soil, st.frames.grow)

/** Mutate config through fn (or replace it) and bump mtime, like ConfigStore.update/save. */
export function bumpConfig(st: MockState, fn?: (c: PlantConfig) => void | PlantConfig): void {
  if (fn) { const r = fn(st.cfg); if (r) st.cfg = r }
  st.mtime = Math.max(st.mtime + 1, Date.now() * 1000)
  st.warnings = []
}

export function addEvent(st: MockState, type: string, data: Record<string, unknown>, ts = Date.now()): EventRow {
  const ev: EventRow = { id: st.nextEventId++, ts: iso(ts), type, data }
  st.events.unshift(ev)
  if (st.events.length > 500) st.events.length = 500
  return ev
}

export const configDoc = (st: MockState): ConfigDoc => ({ config: structuredClone(st.cfg), path: '/home/pi/plant/data/config.json', mtime: st.mtime, warnings: [...st.warnings], check: checkConfig(st.cfg) })

export function ledStatus(st: MockState): LedStatus {
  const l = st.cfg.led
  const reason = !l.enabled ? 'LED not installed (led.enabled=false)' : 'LED not installed (no gpiozero in the mock)'
  return { installed: false, enabled: l.enabled, driver: l.driver, reason, state: 'off', pin: l.pin, active_high: l.active_high, warmup_s: l.warmup_s, max_on_s: l.max_on_s, since: null, auto_off_at: null, last_reason: st.jobs.length ? 'capture_done' : null }
}

export function stepDone(st: MockState): CameraStatus['done'] {
  const c = st.cfg, rois = c.rois
  return {
    focus: Boolean(c.capture.lens_position && c.capture.exposure_us), scale: Boolean(c.qc.px_per_cm_ref), roi: rois.length > 0,
    treat: rois.length > 0 && rois.every((r) => r.treat === 'stable' || r.treat === 'fluct'), shot: st.calibExists,
  }
}

const outOfFrame = (r: Roi, [W, H]: [number, number]) => r.x < 0 || r.y < 0 || r.x + r.w > W || r.y + r.h > H

export function latestRaw(st: MockState): string | null {
  const j = st.jobs.find((x) => x.img_file && x.state === 'done')
  if (j?.img_file) return j.img_file
  const g = [...st.frames.grow].sort((a, b) => b.ts - a.ts).find((r) => r.img_file)
  return g?.img_file ?? null
}

export function cameraStatus(st: MockState): CameraStatus {
  const c = st.cfg, d = stepDone(st), s = st.setup
  return {
    msg: s.msg, msg_level: s.level, done: d, all: Object.values(d).every(Boolean), mode: c.treat_mode as CameraStatus['mode'],
    naming: s.order !== null, order: s.order ? [...s.order] : null, pots: c.rois.map((r) => ({ id: r.plant_id, treat: r.treat })),
    rois: c.rois.map((r) => ({ ...r, out: outOfFrame(r, c.capture.size) })), ppc: Math.round((s.ppcFixed ?? c.qc.px_per_cm_ref ?? 0) * 10) / 10,
    nroi: c.rois.length, cm: s.cm, pts: s.pts.map((p) => [...p] as [number, number]), pot_cm: c.layout.pot_cm,
    capture: structuredClone(c.capture), last_auto: s.lastAuto,
    calib: { exists: st.calibExists, mtime: st.calibMtime, url: st.calibExists ? '/api/camera/calib.jpg' : null }, latest_raw: latestRaw(st),
    state: st.cam.state, driver: 'mock', clients: st.cam.clients, preview: st.cam.preview, paused_for: st.cam.pausedFor, error: null,
    preview_size: [...PREVIEW] as [number, number], capture_size: [...CAP] as [number, number], scale: Math.round(SCALE * 1e6) / 1e6,
    lock_holder_pid: st.job ? 4242 : null, ops_busy: st.cam.opsBusy, quiet_window: null,
  }
}

export function schedule(st: MockState, now = Date.now()): Schedule {
  const c = st.cfg
  const nd = nextOccurrence(c.schedule.dawn, c.tz, now), np = nextOccurrence(c.schedule.pm, c.tz, now)
  return {
    tz: c.tz, dawn: c.schedule.dawn, pm: c.schedule.pm, warmup_s: 0, expected_shot: { dawn: addMinutes(c.schedule.dawn, 0), pm: addMinutes(c.schedule.pm, 0) },
    next: nd <= np ? { phase: 'dawn', at: iso(nd) } : { phase: 'pm', at: iso(np) }, timer: null,
  }
}

export const captureStatus = (st: MockState): CaptureStatus => ({
  job: st.job ? structuredClone(st.job) : null, last: st.jobs[0] ? structuredClone(st.jobs[0]) : null, schedule: schedule(st), led: ledStatus(st),
  camera: { state: st.cam.state, driver: 'mock', preview: st.cam.preview },
})
