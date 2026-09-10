/* `?scenario=` presets: which tables are real, which pots exist, and how far camera setup has gone. */
import type { PlantConfig, Roi } from '@/api/types'
import { emptyFrames, maxTs, type Frames } from './frames'
import { assignedGrid } from './fixtures/config'
import { synth } from './synth'

export const SCENARIOS = ['full', 'env-only', 'none', 'conflict', 'unknown-treat', 'one-group', 'setup-fresh', 'setup-done', 'capture-failed'] as const
export type Scenario = (typeof SCENARIOS)[number]

export function currentScenario(): Scenario {
  if (typeof location === 'undefined') return 'full'
  const s = new URLSearchParams(location.search).get('scenario')
  return (SCENARIOS as readonly string[]).includes(s ?? '') ? (s as Scenario) : 'full'
}

export interface ScenarioSetup { rois: Roi[]; ppc: number; treatMode: string; lens: number; calib: boolean; failedJob: boolean; runStarted: string | null }

export function scenarioSetup(s: Scenario, nowMs = Date.now()): ScenarioSetup {
  const runStarted = new Date(nowMs - 7 * 86_400_000).toISOString().replace(/\.\d{3}Z$/, 'Z')
  if (s === 'setup-fresh') return { rois: [], ppc: 0, treatMode: '', lens: 0, calib: false, failedJob: false, runStarted: null }
  if (s === 'none') return { rois: assignedGrid(), ppc: 30, treatMode: 'random', lens: 1.82, calib: true, failedJob: false, runStarted: null }
  return { rois: assignedGrid(), ppc: 30, treatMode: 'random', lens: 1.82, calib: true, failedJob: s === 'capture-failed', runStarted }
}

const STABLE3: Record<string, string> = { p1: 'stable', p2: 'stable', p3: 'stable' }

export function buildFrames(s: Scenario, cfg: PlantConfig, nowMs = Date.now()): Frames {
  if (s === 'none') return emptyFrames(cfg.tz)
  const d = synth(cfg, s === 'one-group' ? STABLE3 : null, 7, 30, 7, nowMs)
  const fr: Frames = { env: d.env, soil: d.soil, pump: d.pump, grow: d.grow, fake: [], real_pots: new Set(d.soil.map((r) => r.plant_id)), real_env: true, now: null, now_real: null, tz: cfg.tz }
  const real = (rows: { node?: string }[]) => rows.forEach((r) => { if ('node' in r) r.node = 'plant-node' })

  if (s === 'env-only' || s === 'setup-fresh') {
    fr.fake = ['growth', 'pump', 'soil']
    fr.real_pots = new Set()
    real(fr.env)
    fr.now_real = maxTs(fr.env)
  } else {
    real(fr.env); real(fr.soil); real(fr.pump)
    fr.grow.forEach((r) => { r.img_file = `${new Date(r.ts).toISOString().slice(0, 10)}_${r.phase === 'dawn' ? '0550' : '1500'}.jpg` })
    fr.now_real = maxTs(fr.env, fr.soil, fr.pump, fr.grow)
  }
  if (s === 'conflict') fr.grow.forEach((r) => { if (r.plant_id === 'p2') r.treat = 'fluct' })
  if (s === 'unknown-treat') {
    const last = fr.soil[fr.soil.length - 1]
    for (let i = 5; i >= 1; i--) fr.soil.push({ ...last, ts: last.ts - i * 1_800_000, plant_id: 'p7', treat: 'A', pct: 41.2 + i * 0.1 })
    fr.real_pots.add('p7')
  }
  fr.now = maxTs(fr.env, fr.soil, fr.pump, fr.grow)
  return fr
}
