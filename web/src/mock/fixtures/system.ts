/* /api/system/status for the mock (api/system.py shape; a PC-like host: no systemd, no Pi libs). */
import type { SystemStatus } from '@/api/types'
import { cameraStatus, ledStatus, type MockState } from '../state'
import { iso } from '../time'

export function systemStatus(st: MockState, now = Date.now()): SystemStatus {
  const fr = st.frames
  const maxTs = (rows: { ts: number }[]) => (rows.length ? iso(Math.max(...rows.map((r) => r.ts))) : null)
  const real = (t: 'env' | 'soil' | 'pump' | 'growth', rows: { ts: number }[]) => (fr.fake.includes(t) ? [] : rows)
  const tables = {
    readings: real('env', fr.env), soil: real('soil', fr.soil), pump_log: real('pump', fr.pump), growth: real('growth', fr.grow),
  }
  const counts = Object.fromEntries(Object.entries(tables).map(([k, rows]) => [k, { rows: rows.length, max_ts: maxTs(rows) }]))
  const nrows = Object.values(tables).reduce((a, r) => a + r.length, 0)
  const rawPhotos = new Set(fr.grow.filter((r) => r.img_file).map((r) => r.img_file)).size + st.jobs.filter((j) => j.img_file).length
  const cam = cameraStatus(st)
  return {
    version: '2.0.0', git_rev: 'mock0000', python: '3.11.2', platform: 'mock', hostname: 'plant-hub-demo',
    opencv: '4.10.0', picamera2: null, gpiozero: null,
    tz: st.cfg.tz, time: iso(now), uptime_s: Math.floor((now - st.startedAt) / 1000) + 3 * 86_400 + 4_212, service_uptime_s: Math.floor((now - st.startedAt) / 1000), cpu_temp_c: null,
    data_dir: '/home/pi/plant/data', repo_root: '/home/pi/plant',
    disk: { total: 31_137_890_304, used: 11_984_896_000, free: 19_152_994_304 },
    db: { path: '/home/pi/plant/data/plant.db', exists: nrows > 0, size: nrows > 0 ? 65_536 + nrows * 96 : 0, tables: counts },
    photos: { raw: rawPhotos, debug: rawPhotos * st.cfg.rois.length, mask: rawPhotos * st.cfg.rois.length },
    services: null,
    camera: { state: cam.state, driver: cam.driver, clients: cam.clients, preview: cam.preview, paused_for: cam.paused_for, error: null, preview_size: cam.preview_size, capture_size: cam.capture_size, scale: cam.scale, lock_holder_pid: cam.lock_holder_pid, ops_busy: cam.ops_busy, quiet_window: null },
    led: ledStatus(st),
    mqtt: { connected: true, broker: `${st.cfg.mqtt.host}:${st.cfg.mqtt.port}`, last_msg: fr.now === null ? null : iso(fr.now), messages: st.mqttMessages, error: null },
    ws_clients: 1, web_dist: true, dummy_fill: st.cfg.analysis.dummy_fill, pid: 4242, started_at: iso(st.startedAt),
  }
}
