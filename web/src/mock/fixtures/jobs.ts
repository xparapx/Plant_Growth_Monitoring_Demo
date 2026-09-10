/* Job records (capture/runner.py JobRecord) and the seed event log. */
import type { Job } from '@/api/types'
import type { MockState } from '../state'
import { addEvent } from '../state'
import { iso } from '../time'

export const STEP_NAMES = ['queued', 'lock', 'led_on', 'camera_open', 'controls', 'settle', 'capture', 'led_off', 'measure', 'jsonl', 'publish'] as const

export function newJob(phase: 'dawn' | 'pm', trigger: string, startMs: number, imgFile: string): Job {
  return {
    id: Math.random().toString(16).slice(2, 14).padEnd(12, '0'), phase, trigger, state: 'queued', step: 'queued', started_at: iso(startMs), finished_at: null,
    img_file: imgFile, n_rows: 0, ok_rows: 0, published: false, error: null, steps: [], rows: [], warmup_s: 0, warm_until: null,
    led: { installed: false, state: 'off', reason: 'LED not installed (led.enabled=false)' }, fake: false, drift: null, log: [], publish_error: null,
  }
}

/** capture-failed scenario: yesterday's pm job died in measure. */
export function failedJob(now: number): Job {
  const t0 = now - 20 * 3_600_000
  const j = newJob('pm', 'timer', t0, `${new Date(t0).toISOString().slice(0, 10)}_1500.jpg`)
  const names = [...STEP_NAMES.slice(0, 9), 'failed']
  const waits = [0, 180, 90, 210, 320, 190, 2100, 2040, 110, 640]
  let t = t0
  j.steps = names.map((name, i) => { t += waits[i]; return { name, at: iso(t), ms: i < names.length - 1 ? waits[i + 1] : null } })
  Object.assign(j, { state: 'failed', step: 'failed', finished_at: iso(t), error: 'measure: RuntimeError: ExG threshold found no green pixels in p4 — lighting changed?', n_rows: 6, ok_rows: 0 })
  j.log = ['[LED] skipped — LED not installed (led.enabled=false)', `[${j.img_file}] shot ${j.img_file}`, '[measure] p4: no contour — mask empty']
  return j
}

export function seedEvents(st: MockState, now: number): void {
  addEvent(st, 'mqtt.connect', { rc: 'Success' }, st.startedAt)
  addEvent(st, 'led.skipped', { installed: false, reason: 'capture' }, st.startedAt + 5_000)
  for (const j of [...st.jobs].reverse()) {
    addEvent(st, `capture.${j.state}`, { id: j.id, phase: j.phase, trigger: j.trigger, ok_rows: j.ok_rows, n_rows: j.n_rows, img_file: j.img_file, error: j.error }, new Date(j.finished_at ?? j.started_at).getTime())
  }
  if (st.scenario !== 'none' && st.scenario !== 'setup-fresh') {
    addEvent(st, 'setup.save', { msg: '현재 설정을 다시 저장했습니다' }, now - 3 * 3_600_000)
    addEvent(st, 'config.changed', { keys: ['schedule'] }, now - 2 * 3_600_000)
  }
}
