import { createContext, useContext } from 'react'
import type { ActionResult, CameraAction, CameraStatus } from '@/api/types'

export type Mode = 'idle' | 'measure' | 'naming'
export const STEP_KEYS = ['focus', 'scale', 'roi', 'treat', 'shot'] as const

export interface SetupCtx {
  status: CameraStatus
  /** Fire an action; returns null on error (message kept in `error`). */
  run: (name: CameraAction, body?: Record<string, unknown>) => Promise<ActionResult | null>
  pending: CameraAction | null
  /** True while a capture job holds the camera — every action button is disabled. */
  disabled: boolean
  error: string | null
  mode: Mode
  measure: boolean
  setMeasure: (v: boolean) => void
  activeStep: number
}

export const Ctx = createContext<SetupCtx | null>(null)

export function useSetup(): SetupCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('useSetup outside SetupProvider')
  return c
}
