import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { useCameraAction } from '@/api/mutations'
import type { CameraAction, CameraStatus } from '@/api/types'
import { Ctx, STEP_KEYS, type Mode, type SetupCtx } from './setupCtx'

export function SetupProvider({ status, children }: { status: CameraStatus; children: ReactNode }) {
  const act = useCameraAction()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<CameraAction | null>(null)
  const [measure, setMeasure] = useState(false)

  const activeStep = useMemo(() => {
    const i = STEP_KEYS.findIndex((k) => !status.done[k])
    return i < 0 ? STEP_KEYS.length - 1 : i
  }, [status.done])

  // Scale step becomes active -> measuring on by default; leaving it -> off.
  useEffect(() => { setMeasure(activeStep === 1) }, [activeStep])

  const run = useCallback<SetupCtx['run']>(async (name, body) => {
    setPending(name)
    try {
      const res = await act.mutateAsync({ name, body })
      setError(null)
      return res
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : e instanceof Error ? e.message : String(e))
      return null
    } finally {
      setPending(null)
    }
  }, [act])

  const disabled = status.ops_busy === 'job' || status.preview === 'paused_capture'
  const mode: Mode = status.naming ? 'naming' : measure ? 'measure' : 'idle'
  const value = useMemo<SetupCtx>(
    () => ({ status, run, pending, disabled, error, mode, measure, setMeasure, activeStep }),
    [status, run, pending, disabled, error, mode, measure, activeStep],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
