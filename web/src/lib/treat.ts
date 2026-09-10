import { cssVar } from '@/app/theme'

export const TREAT_NAME: Record<string, string> = { stable: 'STABLE', fluct: 'FLUCT' }
export const TREAT_LONG: Record<string, string> = { stable: 'STABLE', fluct: 'FLUCTUATING' }
export const TREAT_KO: Record<string, string> = { stable: '꾸준군', fluct: '널뜀군' }
/** Short letter used in the mockup ("S 412 mL", "P1 S"). */
export const TREAT_LETTER: Record<string, string> = { stable: 'S', fluct: 'F' }

type Kind = 'fill' | 'ink' | 'on'
const SUFFIX: Record<Kind, string> = { fill: '', ink: '-ink', on: '-on' }

/** Resolved hex for a treatment: `fill` = chip/line colour, `ink` = text on the page, `on` = text on the fill. */
export function trtColor(treat: string | null | undefined, kind: Kind = 'ink'): string {
  const t = treat === 'stable' || treat === 'fluct' ? treat : null
  if (!t) return cssVar(kind === 'on' ? '--bg' : kind === 'ink' ? '--ink-muted' : '--ink-faint')
  return cssVar(`--${t}${SUFFIX[kind]}`)
}

/** CSS variable reference (for inline styles that must follow the theme without re-render). */
export function trtVar(treat: string | null | undefined, kind: Kind = 'ink'): string {
  const t = treat === 'stable' || treat === 'fluct' ? treat : null
  if (!t) return `var(${kind === 'on' ? '--bg' : kind === 'ink' ? '--ink-muted' : '--ink-faint'})`
  return `var(--${t}${SUFFIX[kind]})`
}

export const ENV_VAR: Record<string, string> = { vpd: '--env-vpd', temp: '--env-temp', hum: '--env-hum', co2: '--env-co2', lux: '--env-lux' }
