import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import { qk } from './queries'
import type { ActionResult, CameraAction, CameraStatus, ConfigDoc, Job, LedStatus, PlantConfig, ReplayResult } from './types'

export function useCameraAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, body }: { name: CameraAction; body?: Record<string, unknown> }) =>
      apiFetch<ActionResult>(`/api/camera/actions/${name}`, { method: 'POST', body: body ?? {} }),
    onSuccess: (res) => {
      qc.setQueryData<CameraStatus>(qk.camera.status, res.status)
      qc.invalidateQueries({ queryKey: qk.config })
      qc.invalidateQueries({ queryKey: qk.camera.drift })
    },
  })
}

export function useCaptureRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { phase: 'auto' | 'dawn' | 'pm'; force?: boolean }) =>
      apiFetch<{ job: Job }>(`/api/capture/run?phase=${p.phase}${p.force ? '&force=1' : ''}`, { method: 'POST' }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: qk.capture.status })
      qc.invalidateQueries({ queryKey: qk.camera.status })
    },
  })
}

export function useCaptureCancel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<{ cancelled: boolean }>('/api/capture/cancel', { method: 'POST' }),
    onSettled: () => qc.invalidateQueries({ queryKey: qk.capture.status }),
  })
}

export function useLedMutation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (kind: 'on' | 'off' | 'test') => apiFetch<LedStatus>(`/api/led/${kind}${kind === 'test' ? '?seconds=2' : ''}`, { method: 'POST' }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: qk.led })
      qc.invalidateQueries({ queryKey: qk.capture.status })
    },
  })
}

export function useConfigSave() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ patch, mtime }: { patch: Partial<PlantConfig> | Record<string, unknown>; mtime?: number }) =>
      apiFetch<ConfigDoc>('/api/config', { method: 'PATCH', body: patch, headers: mtime ? { 'If-Match': String(mtime) } : {} }),
    onSuccess: (doc) => {
      qc.setQueryData(qk.config, doc)
      qc.invalidateQueries({ queryKey: qk.summary })
      qc.invalidateQueries({ queryKey: qk.camera.status })
      qc.invalidateQueries({ queryKey: qk.capture.status })
    },
  })
}

export function useReplayPublish() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<ReplayResult>('/api/capture/replay', { method: 'POST' }),
    onSettled: () => qc.invalidateQueries({ queryKey: qk.capture.status }),
  })
}
