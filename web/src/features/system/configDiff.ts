import type { PlantConfig } from '@/api/types'

export type SectionKey = keyof PlantConfig

/** Top-level sections whose JSON differs between the loaded doc and the draft. */
export function changedSections(base: PlantConfig, draft: PlantConfig): SectionKey[] {
  const keys = new Set<SectionKey>([...(Object.keys(base) as SectionKey[]), ...(Object.keys(draft) as SectionKey[])])
  return [...keys].filter((k) => JSON.stringify(base[k]) !== JSON.stringify(draft[k]))
}

export function pickSections(draft: PlantConfig, keys: SectionKey[]): Partial<PlantConfig> {
  const out: Record<string, unknown> = {}
  for (const k of keys) out[k] = draft[k]
  return out as Partial<PlantConfig>
}

export function parseConfigJson(text: string): { ok: true; value: PlantConfig } | { ok: false; error: string } {
  try {
    const v = JSON.parse(text)
    if (typeof v !== 'object' || v === null || Array.isArray(v)) return { ok: false, error: '최상위는 객체여야 합니다' }
    return { ok: true, value: v as PlantConfig }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}
