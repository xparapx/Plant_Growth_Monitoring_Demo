import { cssVar } from '@/app/theme'

export const TREAT_NAME: Record<string, string> = { stable: 'STABLE', fluct: 'FLUCTUATING' }
export const TREAT_KO: Record<string, string> = { stable: '꾸준군', fluct: '널뜀군' }

/** Resolved hex for a treatment (fill or ink). */
export function trtColor(treat: string | null | undefined, kind: 'fill' | 'ink' = 'ink'): string {
  const t = treat === 'stable' || treat === 'fluct' ? treat : null
  if (!t) return cssVar(kind === 'ink' ? '--ink-muted' : '--ink-faint')
  return cssVar(kind === 'ink' ? `--${t}-ink` : `--${t}`)
}

/** CSS variable reference (for inline styles that must follow the theme without re-render). */
export function trtVar(treat: string | null | undefined, kind: 'fill' | 'ink' = 'ink'): string {
  const t = treat === 'stable' || treat === 'fluct' ? treat : null
  if (!t) return `var(${kind === 'ink' ? '--ink-muted' : '--ink-faint'})`
  return `var(--${t}${kind === 'ink' ? '-ink' : ''})`
}

export const ENV_VAR: Record<string, string> = { vpd: '--env-vpd', temp: '--env-temp', hum: '--env-hum', co2: '--env-co2', lux: '--env-lux' }
