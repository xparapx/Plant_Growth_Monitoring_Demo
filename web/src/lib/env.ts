import type { EnvKey } from '@/api/types'

/** Gauge ranges and "optimal" bands per environment variable (mockup captions: 10–40, 0–100, 0–3, 0.4–2k, 0–60k). */
export const ENV_GAUGE: Record<EnvKey, { range: [number, number]; optimal: [number, number]; rangeLabel: string; label: string }> = {
  temp: { range: [10, 40], optimal: [18, 28], rangeLabel: '10–40', label: '온도' },
  hum: { range: [0, 100], optimal: [40, 70], rangeLabel: '0–100', label: '습도' },
  vpd: { range: [0, 3], optimal: [0.8, 1.5], rangeLabel: '0–3', label: 'VPD' },
  co2: { range: [400, 2000], optimal: [700, 1200], rangeLabel: '0.4–2k', label: 'CO₂' },
  lux: { range: [0, 60000], optimal: [10000, 40000], rangeLabel: '0–60k', label: '조도' },
}

/** Mockup order: 온도 · 습도 · VPD · CO₂ · 조도. */
export const ENV_ORDER: EnvKey[] = ['temp', 'hum', 'vpd', 'co2', 'lux']
