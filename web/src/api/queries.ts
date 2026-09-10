import { QueryClient, keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type {
  AlignmentTrend, CameraStatus, Canopy, CaptureStatus, ConfigDoc, Drift, Droop, DroopTimeline, EnvSeries, EventsList,
  Histogram, ImagesList, JobsList, LedStatus, LogLines, PumpRecent, Reference, Rgr, Silhouettes, SoilSeries, Summary,
  SystemStatus, Water,
} from './types'
import { liveStore } from '@/live/liveStore'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 55_000,
      retry: 1,
      refetchOnWindowFocus: true,
      placeholderData: keepPreviousData,
      refetchInterval: () => (liveStore.get().connected ? 300_000 : 60_000),
    },
  },
})

export const qk = {
  summary: ['summary'] as const,
  env: (bucket: string, from?: string) => ['env', bucket, from ?? ''] as const,
  soil: (bucket: string, pots?: string, from?: string) => ['soil', bucket, pots ?? '', from ?? ''] as const,
  pumpRecent: (n: number) => ['pump', 'recent', n] as const,
  analytics: (name: string) => ['analytics', name] as const,
  camera: { status: ['camera', 'status'] as const, drift: ['camera', 'drift'] as const },
  capture: { status: ['capture', 'status'] as const, jobs: (n: number) => ['capture', 'jobs', n] as const },
  led: ['led'] as const,
  config: ['config'] as const,
  system: ['system'] as const,
  images: (kind: string) => ['images', kind] as const,
  events: (type?: string) => ['events', type ?? ''] as const,
  logs: (unit: string) => ['logs', unit] as const,
}

export const useSummary = () => useQuery({ queryKey: qk.summary, queryFn: () => apiFetch<Summary>('/api/summary') })
export const useEnv = (bucket = 'auto', from?: string) =>
  useQuery({ queryKey: qk.env(bucket, from), queryFn: () => apiFetch<EnvSeries>(`/api/env?bucket=${bucket}${from ? `&from=${from}` : ''}`) })
export const useSoil = (bucket = 'auto', pots?: string, from?: string) =>
  useQuery({ queryKey: qk.soil(bucket, pots, from), queryFn: () => apiFetch<SoilSeries>(`/api/soil?bucket=${bucket}${pots ? `&pots=${pots}` : ''}${from ? `&from=${encodeURIComponent(from)}` : ''}`) })
export const usePumpRecent = (n = 5) => useQuery({ queryKey: qk.pumpRecent(n), queryFn: () => apiFetch<PumpRecent>(`/api/pump/recent?n=${n}`) })

type AnalyticsMap = {
  histogram: Histogram; 'alignment-trend': AlignmentTrend; droop: Droop; 'droop-timeline': DroopTimeline
  canopy: Canopy; silhouettes: Silhouettes; rgr: Rgr; water: Water; reference: Reference
}
export function useAnalytics<K extends keyof AnalyticsMap>(name: K, enabled = true) {
  return useQuery({ queryKey: qk.analytics(name), queryFn: () => apiFetch<AnalyticsMap[K]>(`/api/analytics/${name}`), enabled })
}

export const useCameraStatus = (enabled = true) =>
  useQuery({ queryKey: qk.camera.status, queryFn: () => apiFetch<CameraStatus>('/api/camera/status'), enabled, refetchInterval: enabled ? 5_000 : false, staleTime: 2_000 })
export const useDrift = (enabled = true) =>
  useQuery({ queryKey: qk.camera.drift, queryFn: () => apiFetch<Drift>('/api/camera/drift'), enabled, staleTime: 30_000 })
export const useCaptureStatus = () =>
  useQuery({ queryKey: qk.capture.status, queryFn: () => apiFetch<CaptureStatus>('/api/capture/status'), refetchInterval: 15_000, staleTime: 5_000 })
export const useCaptureJobs = (n = 30) => useQuery({ queryKey: qk.capture.jobs(n), queryFn: () => apiFetch<JobsList>(`/api/capture/jobs?limit=${n}`) })
export const useLedStatus = () => useQuery({ queryKey: qk.led, queryFn: () => apiFetch<LedStatus>('/api/led') })
export const useConfig = () => useQuery({ queryKey: qk.config, queryFn: () => apiFetch<ConfigDoc>('/api/config') })
export const useSystem = () => useQuery({ queryKey: qk.system, queryFn: () => apiFetch<SystemStatus>('/api/system/status'), refetchInterval: 30_000 })
export const useImages = (kind: string, enabled = true) =>
  useQuery({ queryKey: qk.images(kind), queryFn: () => apiFetch<ImagesList>(`/api/images?kind=${kind}&limit=60`), enabled })
export const useEvents = (type?: string) =>
  useQuery({ queryKey: qk.events(type), queryFn: () => apiFetch<EventsList>(`/api/events?limit=100${type ? `&type=${type}` : ''}`) })
export const useLogs = (unit: string, enabled = true) =>
  useQuery({ queryKey: qk.logs(unit), queryFn: () => apiFetch<LogLines>(`/api/system/logs?unit=${unit}&lines=120`), enabled })
