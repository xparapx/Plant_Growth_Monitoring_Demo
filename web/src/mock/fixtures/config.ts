/* Default config.json (config_model.py), roi grid (roi_tools.grid_rois), config_check.check() port and PATCH helpers. */
import type { CheckReport, PlantConfig, Roi } from '@/api/types'

export const CAP: [number, number] = [4608, 2592]
export const PREVIEW: [number, number] = [1280, 720]
export const SCALE = PREVIEW[0] / CAP[0]

export function gridRois(capW: number, capH: number, cols: number, rows: number, margin = 0.04): Roi[] {
  cols = Math.max(1, Math.floor(cols)); rows = Math.max(1, Math.floor(rows))
  const mx = Math.floor(capW * margin), my = Math.floor(capH * margin)
  const cw = Math.floor((capW - 2 * mx) / cols), ch = Math.floor((capH - 2 * my) / rows)
  const side = Math.floor(Math.min(cw, ch) * 0.92)
  const out: Roi[] = []
  let n = 1
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const cx = mx + cw * c + Math.floor(cw / 2), cy = my + ch * r + Math.floor(ch / 2)
    out.push({ plant_id: `p${n++}`, treat: '', x: cx - Math.floor(side / 2), y: cy - Math.floor(side / 2), w: side, h: side })
  }
  return out
}

/** The 3x2 default grid with p1-p3 stable / p4-p6 fluct (matches the synth roster). */
export const assignedGrid = (): Roi[] => gridRois(CAP[0], CAP[1], 3, 2).map((r, i) => ({ ...r, treat: i < 3 ? 'stable' : 'fluct' }))

export interface ConfigOpts { rois: Roi[]; ppc: number; treatMode: string; lens: number; runStarted: string | null }

export function defaultConfig(o: ConfigOpts): PlantConfig {
  return {
    version: 2, tz: 'Asia/Seoul',
    layout: { cols: 3, rows: 2, pot_cm: 15, gap_cm: 20 },
    capture: { size: [...CAP] as [number, number], lens_position: o.lens, exposure_us: 20000, gain: 2, colour_gains: [1.8, 1.6] },
    rois: o.rois, treat_mode: o.treatMode, run_started: o.runStarted,
    qc: { px_per_cm_ref: o.ppc, edge_tol: 0.02, drift_warn_px: 8, drift_fail_px: 40, drift_resp_min: 0.05 },
    bands: { raw: { stable: [1900, 1940], fluct: [1820, 2020] }, cal_default: [2120, 1750], cal: {} },
    analysis: { tol_pp: 2, sep_ratio: 2, hist_bins: 44, soil_days: 7, pump_limit: 200, dummy_fill: 'auto', env_interval_min: 5, soil_interval_min: 5, cam_interval_min: 720 },
    led: { enabled: false, driver: 'noop', pin: 17, active_high: true, warmup_s: 300, max_on_s: 1200 },
    schedule: { dawn: '05:50', pm: '15:00' },
    mqtt: { host: 'localhost', port: 1883, growth_topic: 'plant/tray/growth' },
    preview: { size: [...PREVIEW] as [number, number], jpeg_quality: 80, frame_ms: 80 },
  }
}

export function checkConfig(cfg: PlantConfig): CheckReport {
  const bad: string[] = [], warn: string[] = [], lines: CheckReport['lines'] = []
  const line = (section: string, k: string, v: unknown, note = '') => lines.push({ section, k, v, note })
  const [W, H] = cfg.capture.size, cap = cfg.capture, ppc = cfg.qc.px_per_cm_ref, rois = cfg.rois
  line('촬영 조건', '해상도', `${W} x ${H} px`)
  line('촬영 조건', 'lens_position', cap.lens_position, '디옵터 = 1/거리(m)')
  line('촬영 조건', 'exposure_us', cap.exposure_us, cap.exposure_us ? `= 1/${Math.round(1e6 / cap.exposure_us)} 초` : '')
  line('촬영 조건', 'gain', cap.gain)
  line('촬영 조건', 'colour_gains', cap.colour_gains, '(적색, 청색)')
  if (cap.gain > 4) warn.push(`gain ${cap.gain} — 조명이 어둡습니다. 노이즈가 ExG 분리를 방해합니다`)
  if (!cap.lens_position) bad.push('lens_position 이 비어 있습니다 — [자동 측정] 을 실행하세요')
  if (ppc > 0) {
    line('배율', 'px_per_cm_ref', `${ppc.toFixed(1)} px/cm`)
    line('배율', '프레임 실제 크기', `${(W / ppc).toFixed(1)} x ${(H / ppc).toFixed(1)} cm`)
    line('배율', '1 px', `${(10 / ppc).toFixed(2)} mm`)
  } else {
    line('배율', 'px_per_cm_ref', '없음')
    bad.push('px_per_cm_ref 가 0 입니다 — area_cm2 가 null 이 되고 측정 행이 ok=0 으로 기록되어 대시보드가 전부 걸러냅니다')
  }
  line('ROI', '칸 수', rois.length)
  if (!rois.length) bad.push('rois 가 비어 있습니다 — [잎 찾아 배치] 또는 [격자로 나누기] 를 누르세요')
  else {
    const empty = rois.filter((r) => r.treat !== 'stable' && r.treat !== 'fluct').map((r) => r.plant_id)
    if (empty.length) warn.push(`처리군이 비어 있는 ROI: ${empty.join(', ')} — [무작위 배정] 을 누르세요`)
    const ids = new Set(rois.map((r) => r.plant_id))
    if (ids.size !== rois.length) bad.push('plant_id 가 중복됩니다 — [이름 다시 매기기] 를 누르세요')
    line('ROI', '처리군', rois.map((r) => `${r.plant_id}:${r.treat || '-'}`).join(' '), cfg.treat_mode ? `mode ${cfg.treat_mode}` : '')
  }
  line('스케줄', 'dawn / pm', `${cfg.schedule.dawn} / ${cfg.schedule.pm}`, `tz ${cfg.tz}`)
  line('LED', 'enabled / driver', `${cfg.led.enabled ? 'True' : 'False'} / ${cfg.led.driver}`, `pin ${cfg.led.pin} warm-up ${cfg.led.warmup_s}s`)
  if (cfg.led.enabled && cfg.led.driver === 'noop') warn.push('led.enabled 인데 driver 가 noop 입니다 — LED 가 켜지지 않습니다')
  return { bad, warn, lines, ok: bad.length === 0 }
}

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

/** config_model validators that matter for the editor: returns an error message or null. */
export function validateConfig(cfg: PlantConfig): string | null {
  for (const k of ['dawn', 'pm'] as const) {
    const v = cfg.schedule?.[k]
    if (typeof v !== 'string' || !HHMM.test(v)) return `schedule.${k}: '${String(v)}' 는 HH:MM 형식이 아닙니다`
  }
  if (!['auto', 'on', 'off'].includes(cfg.analysis?.dummy_fill)) return `analysis.dummy_fill: ${String(cfg.analysis?.dummy_fill)} — auto|on|off 만 허용됩니다`
  if (!(cfg.layout?.cols >= 1) || !(cfg.layout?.rows >= 1)) return 'layout.cols / rows 는 1 이상이어야 합니다'
  if (!(cfg.mqtt?.port > 0 && cfg.mqtt.port < 65536)) return 'mqtt.port 가 범위를 벗어났습니다'
  try { new Intl.DateTimeFormat('en-US', { timeZone: cfg.tz }) } catch { return `tz: 알 수 없는 시간대 '${cfg.tz}'` }
  return null
}

export function deepMerge<T>(base: T, patch: unknown): T {
  if (!isObj(base) || !isObj(patch)) return patch as T
  const out: Record<string, unknown> = { ...(base as Record<string, unknown>) }
  for (const [k, v] of Object.entries(patch as Record<string, unknown>)) out[k] = isObj(v) && isObj(out[k]) ? deepMerge(out[k], v) : v
  return out as T
}
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
