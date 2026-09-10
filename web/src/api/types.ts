/* Typed mirror of the plantsvc JSON contract (snake_case, ISO-8601 UTC timestamps). */

export type Treat = 'stable' | 'fluct'
export type TableName = 'env' | 'soil' | 'pump' | 'growth'
export type EnvKey = 'vpd' | 'temp' | 'hum' | 'co2' | 'lux'
export const ENV_KEYS: EnvKey[] = ['vpd', 'temp', 'hum', 'co2', 'lux']

export interface Meta { now: string | null; now_real: string | null; dummy: TableName[] }

export interface EnvStat {
  label: string; unit: string; digits: number
  value: number | null; delta_1d: number | null; missing: boolean; spark: (number | null)[]
}
export interface NodeHealth {
  name: string; kind: 'env' | 'pot' | 'cam'; pot: string | null; real: boolean
  state: 'ok' | 'amber' | 'bad' | 'off'; minutes_ago: number | null; every_min: number; stuck: boolean; last_ts: string | null
}
export interface Alert {
  level: 'error' | 'warn' | 'info'; code: string; text: string
  pots?: string[]; keys?: string[]; labels?: string[]; sql?: string | null; detail?: Record<string, Record<string, string>>
}
export interface Validity {
  tol_pp: number; sep_ratio: number; enough_groups: boolean; groups: Record<string, string[]>
  mu: Record<string, number>; sd: Record<string, number>; n: Record<string, number>
  dmu: number | null; aligned: boolean | null; ratio: number | null; separated: boolean | null
}
export interface LedStatus {
  installed: boolean; enabled: boolean; driver: string; reason: string | null; state: 'on' | 'off'
  pin: number; active_high: boolean; warmup_s: number; max_on_s: number
  since: string | null; auto_off_at: string | null; last_reason: string | null
}
export interface Summary extends Meta {
  sources: Record<TableName, 'real' | 'dummy' | 'none'>
  pots: { id: string; treat: string | null; real: boolean }[]
  groups: Record<string, string[]>; ncol: number
  conflicts: { pot: string; sources: Record<string, string> }[]
  unknown_labels: string[]; suggested_sql: string | null
  env: Record<EnvKey, EnvStat>; nodes: NodeHealth[]; alerts: Alert[]; validity: Validity
  run_started: string | null; tz: string; real_env: boolean; capture: { driver: string }; led: LedStatus
}
export interface EnvSeries extends Meta {
  bucket: number
  series: { ts: string[]; n?: number[] } & Partial<Record<'temp' | 'hum' | 'press' | 'vpd' | 'lux' | 'co2', (number | null)[]>>
  current: Record<EnvKey, number | null>; delta_24h: Record<EnvKey, number | null>; missing: Record<EnvKey, boolean>
}
export interface SoilSeries extends Meta {
  bucket: number; groups: Record<string, string[]>; basis: string
  band_pct: Record<string, [number, number]>; yrange: [number, number]
  pots: { plant_id: string; treat: string | null; ts: string[]; pct: (number | null)[]; n: number[] | null }[]
}
export interface PumpRecentRow {
  ts: string; ago_h: number | null; pot: string; plant_id: string; treat: string | null
  pump_s: number | null; before: number | null; after: number | null; rise: number | null; reason: string | null
}
export interface PumpRecent extends Meta { rows: PumpRecentRow[] }
export interface Histogram extends Meta {
  edges: number[]; groups: Record<string, { prob: number[]; mu: number; sd: number; n: number }>
  e_w: number | null; quantiles: { p05: number | null; p95: number | null; mean: number | null }
}
export interface AlignmentTrend extends Meta { weeks: string[]; groups: Record<string, (number | null)[]> }
export interface Droop extends Meta {
  rows: { pot: string; treat: string | null; day: string; dawn_px: number; pm_px: number; droop_pct: number }[]
  missing: string[]; has_both_phases: boolean
}
export interface DroopTimeline extends Meta { days: string[]; pots: { plant_id: string; treat: string | null; droop_pct: (number | null)[] }[] }
export interface Canopy extends Meta { pots: { plant_id: string; treat: string | null; ts: string[]; area_cm2: (number | null)[] }[] }
export interface SilFrame { ts: string; area_cm2: number | null; area_px: number; contour: [number, number][] }
export interface Silhouettes extends Meta {
  pots: { plant_id: string; treat: string; new: SilFrame; old: SilFrame; gain_pct: number | null; gap_d: number
          base: { ts: string; area_cm2: number | null }; total_pct: number | null; span_d: number; lim: number }[]
  not_enough: string[]
}
export interface Rgr extends Meta {
  pots: { pot: string; treat: string | null; rgr: number; se: number | null; ci95: [number, number] | null; r2: number; n: number }[]
  groups: Record<string, { mean: number; sd: number | null; n: number }>
  cohens_d: number | null; effect: string | null; worst_r2: number | null; comparable: boolean
}
export interface Water extends Meta {
  ml_per_s: number
  groups: Record<string, { total_ml: number; events: number; pots: number; ml_per_pot: number }>
  pots: { plant_id: string; treat: string | null; events: number; total_ml: number; interval_d: number[]; mean_interval_d: number | null; last_interval_d: number | null }[]
  daily: { days: string[]; groups: Record<string, number[]> }
}
export interface Reference extends Meta { p05: number | null; p95: number | null; mean: number | null }

export interface Roi { plant_id: string; treat: string; x: number; y: number; w: number; h: number; out?: boolean }
export interface CaptureSettings { size: [number, number]; lens_position: number; exposure_us: number; gain: number; colour_gains: [number, number] }
export interface CameraStatus {
  msg: string; msg_level: 'info' | 'good' | 'warn'
  done: { focus: boolean; scale: boolean; roi: boolean; treat: boolean; shot: boolean }; all: boolean
  mode: 'random' | 'manual' | ''; naming: boolean; order: number[] | null
  pots: { id: string; treat: string }[]; rois: Roi[]; ppc: number; nroi: number; cm: number; pts: [number, number][]; pot_cm: number
  capture: CaptureSettings; last_auto: Record<string, unknown> | null
  calib: { exists: boolean; mtime: number | null; url: string | null }; latest_raw: string | null
  state: 'closed' | 'opening' | 'open' | 'error'; driver: string; clients: number
  preview: 'live' | 'paused_capture' | 'unavailable'; paused_for: string | null; error: string | null
  preview_size: [number, number]; capture_size: [number, number]; scale: number
  lock_holder_pid: number | null; ops_busy: string | null; quiet_window: { until: string } | null
}
export interface Drift {
  ok: boolean; dx: number; dy: number; mag: number; resp: number; deg: number; scale: number; resp_rs: number
  level: 'unknown' | 'unreliable' | 'ok' | 'drift' | 'fail'; msg: string; cur: string | null; mag_mm: number | null
}
export type CameraAction =
  | 'auto' | 'point' | 'clearpoints' | 'setpot' | 'findleaf' | 'autoroi' | 'rename' | 'cancel_naming' | 'pickroi'
  | 'settreat' | 'shuffle' | 'shoot' | 'save' | 'centerroi' | 'open' | 'close'
export interface ActionResult { msg: string; status: CameraStatus }

export type JobState = 'queued' | 'running' | 'done' | 'failed' | 'skipped' | 'cancelled'
export interface JobStep { name: string; at: string; ms: number | null }
export interface Job {
  id: string; phase: string; trigger: string; state: JobState; step: string
  started_at: string; finished_at: string | null; img_file: string | null; n_rows: number; ok_rows: number
  published: boolean; error: string | null; steps: JobStep[]
  rows: { plant_id: string; treat: string | null; area_cm2: number | null; ok: number }[]
  warmup_s: number; warm_until: string | null; led: Partial<LedStatus> | null; fake: boolean
  drift: Drift | null; log: string[]; publish_error: string | null
}
export interface Schedule {
  tz: string; dawn: string; pm: string; warmup_s: number; expected_shot: { dawn: string; pm: string }
  next: { phase: 'dawn' | 'pm'; at: string }; timer: { unit: string; active: boolean; next: string | null; last: string | null } | null
}
export interface CaptureStatus { job: Job | null; last: Job | null; schedule: Schedule; led: LedStatus; camera: { state: string; driver: string; preview: string } }
export interface JobsList { jobs: Job[] }
export interface ReplayResult { last_db_ts: string; sent: number; skipped: number; errors: string[] }

export interface CheckReport { bad: string[]; warn: string[]; lines: { section: string; k: string; v: unknown; note: string }[]; ok: boolean }
export interface PlantConfig {
  version: number; tz: string
  layout: { cols: number; rows: number; pot_cm: number; gap_cm: number }
  capture: CaptureSettings; rois: Roi[]; treat_mode: string; run_started: string | null
  qc: { px_per_cm_ref: number; edge_tol: number; drift_warn_px: number; drift_fail_px: number; drift_resp_min: number }
  bands: { raw: Record<string, [number, number]>; cal_default: [number, number]; cal: Record<string, [number, number]> }
  analysis: { tol_pp: number; sep_ratio: number; hist_bins: number; soil_days: number; pump_limit: number; dummy_fill: 'auto' | 'on' | 'off'; env_interval_min: number; soil_interval_min: number; cam_interval_min: number }
  led: { enabled: boolean; driver: string; pin: number; active_high: boolean; warmup_s: number; max_on_s: number }
  schedule: { dawn: string; pm: string }
  mqtt: { host: string; port: number; growth_topic: string }
  preview: { size: [number, number]; jpeg_quality: number; frame_ms: number }
}
export interface ConfigDoc { config: PlantConfig; path: string; mtime: number; warnings: string[]; check: CheckReport }

export interface ServiceState { active: string | null; sub?: string | null; since?: string | null; enabled?: string | null; error?: string }
export interface SystemStatus {
  version: string; git_rev: string | null; python: string; platform: string; hostname: string
  opencv: string | null; picamera2: string | null; gpiozero: string | null
  tz: string; time: string; uptime_s: number | null; service_uptime_s: number; cpu_temp_c: number | null
  data_dir: string; repo_root: string; disk: { total: number; used: number; free: number }
  db: { path: string; exists: boolean; size: number; tables: Record<string, { rows: number; max_ts: string | null }> }
  photos: Record<string, number>; services: Record<string, ServiceState> | null
  camera: Partial<CameraStatus>; led: LedStatus
  mqtt: { connected: boolean; broker: string | null; last_msg?: string | null; messages?: number; error?: string | null; disabled?: boolean }
  ws_clients: number; web_dist: boolean; dummy_fill: string; pid: number; started_at: string
}
export interface ImageFile { name: string; size: number; mtime: number; stem: string | null; plant_id: string | null; fake: boolean; url: string }
export interface ImagesList { kind: string; files: ImageFile[] }
export interface EventRow { id: number; ts: string; type: string; data: Record<string, unknown> }
export interface EventsList { events: EventRow[]; now: string }
export interface LogLines { unit: string; lines: string[]; available: boolean; error?: string }

export type LiveType = 'hello' | 'pong' | 'env' | 'soil' | 'pump' | 'growth' | 'capture.progress' | 'capture.done' | 'led' | 'config.changed' | 'camera.state' | 'camera.setup' | 'mqtt.state'
export interface LiveEvent<T = unknown> { type: LiveType; ts: string; data: T }
