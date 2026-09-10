import type { Job, JobState } from '@/api/types'
import type { ChipState } from '@/components/ui/StatusChip'
import type { Step } from '@/components/ui/Stepper'
import { ko } from '@/i18n/ko'
import { fmtDuration } from '@/lib/format'

export const STEP_NAMES = ['queued', 'lock', 'led_on', 'warmup', 'camera_open', 'controls', 'settle', 'capture', 'led_off', 'measure', 'jsonl', 'publish'] as const
const TERMINAL: readonly string[] = ['done', 'failed', 'skipped', 'cancelled']
const LED_STEPS: readonly string[] = ['led_on', 'warmup']

type StepKey = keyof typeof ko.capture.steps
export const stepLabel = (name: string): string => (ko.capture.steps as Record<string, string>)[name as StepKey] ?? name

export const stateChip = (s: JobState | string): ChipState =>
  s === 'done' ? 'ok' : s === 'failed' ? 'bad' : s === 'skipped' || s === 'cancelled' ? 'amber' : s === 'running' ? 'info' : 'off'

export const stateLabel = (s: string): string => stepLabel(s)

export const phaseLabel = (p: string): string => (ko.capture.phase as Record<string, string>)[p] ?? p

export function jobDuration(j: Job): string {
  if (!j.finished_at) return '—'
  return fmtDuration((new Date(j.finished_at).getTime() - new Date(j.started_at).getTime()) / 1000)
}

/** Build HStepper steps for a job (or an idle list when job is null). */
export function jobSteps(job: Job | null): Step[] {
  const passed = new Set((job?.steps ?? []).map((s) => s.name))
  const ledSkipped = !!job?.led && !job.led.installed
  const terminal = job ? TERMINAL.includes(job.step) : false
  const failedAt = job?.state === 'failed' ? lastRealStep(job) : null
  return STEP_NAMES.map((name) => {
    const skipped = ledSkipped && LED_STEPS.includes(name)
    const active = !!job && job.step === name && !terminal
    const done = !!job && (passed.has(name) || (terminal && job.state === 'done')) && !active && !skipped
    return { id: name, title: stepLabel(name), active, done, skipped, failed: failedAt === name }
  })
}

function lastRealStep(job: Job): string | null {
  for (let i = job.steps.length - 1; i >= 0; i--) if (!TERMINAL.includes(job.steps[i].name)) return job.steps[i].name
  return null
}
