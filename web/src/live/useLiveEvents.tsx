import { useEffect, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { CaptureStatus, Job, LedStatus, LiveEvent } from '@/api/types'
import { qk } from '@/api/queries'
import { liveStore } from './liveStore'
import { onLive, startLive } from './ws'

/** WS event -> query invalidation / direct cache updates. */
export function LiveEventsProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  useEffect(() => {
    startLive()
    const soilTimers: { t?: number } = {}
    const inv = (...keys: readonly (readonly unknown[])[]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: k as unknown[] }))
    const off = onLive((ev: LiveEvent) => {
      const data = (ev.data ?? {}) as Record<string, unknown>
      switch (ev.type) {
        case 'env':
          liveStore.touch('env')
          inv(qk.summary, ['env'])
          break
        case 'soil': {
          const row = (data.row ?? {}) as { plant_id?: string }
          liveStore.touch('soil', row.plant_id ?? null)
          window.clearTimeout(soilTimers.t)
          soilTimers.t = window.setTimeout(() => inv(qk.summary, ['soil'], qk.analytics('histogram'), qk.analytics('alignment-trend'), qk.analytics('water')), 2000)
          break
        }
        case 'pump': {
          const row = (data.row ?? {}) as { plant_id?: string }
          liveStore.touch('pump', row.plant_id ?? null)
          if (!data.retained) inv(qk.summary, ['pump'], qk.analytics('water'))
          break
        }
        case 'growth':
          liveStore.touch('growth')
          inv(qk.summary, qk.analytics('silhouettes'), qk.analytics('rgr'), qk.analytics('droop'), qk.analytics('droop-timeline'), qk.analytics('canopy'), ['capture'])
          break
        case 'capture.progress':
        case 'capture.done': {
          const job = ev.data as Job
          qc.setQueryData<CaptureStatus>(qk.capture.status, (old) =>
            old ? { ...old, job: job.state === 'running' || job.state === 'queued' ? job : null, last: job.state === 'running' || job.state === 'queued' ? old.last : job } : old)
          if (ev.type === 'capture.done') inv(qk.capture.status, ['capture', 'jobs'], qk.camera.status, qk.images('raw'), qk.led)
          else inv(qk.camera.status)
          break
        }
        case 'led':
          qc.setQueryData<LedStatus>(qk.led, ev.data as LedStatus)
          qc.setQueryData<CaptureStatus>(qk.capture.status, (old) => (old ? { ...old, led: ev.data as LedStatus } : old))
          break
        case 'config.changed':
          inv(qk.config, qk.summary, qk.camera.status, qk.capture.status)
          break
        case 'camera.state':
        case 'camera.setup':
          inv(qk.camera.status)
          break
        case 'mqtt.state':
          inv(qk.system)
          break
        default:
          break
      }
    })
    return off
  }, [qc])
  return <>{children}</>
}
