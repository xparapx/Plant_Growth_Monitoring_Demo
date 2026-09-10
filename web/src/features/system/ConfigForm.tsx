import type { PlantConfig } from '@/api/types'
import { NumberField } from '@/components/ui/NumberField'
import { ko } from '@/i18n/ko'
import { Section, SelectField, TextField, ToggleField } from './fields'
import { S } from './strings'

const T = S.config.sections
const DUMMY = ['auto', 'on', 'off'] as const
const DRIVERS = ['noop', 'auto', 'gpiozero'] as const

export function ConfigForm({ draft, onChange }: { draft: PlantConfig; onChange: (next: PlantConfig) => void }) {
  const upd = (fn: (c: PlantConfig) => void) => { const c = structuredClone(draft); fn(c); onChange(c) }
  const n = (v: number | '') => (v === '' ? 0 : v)
  const { capture: cap, layout, qc, analysis, led, schedule, mqtt } = draft
  return (
    <div className="flex flex-col gap-3">
      <Section title={T.capture} cols={5}>
        <TextField label={S.config.sizeRO} value={`${cap.size[0]} x ${cap.size[1]}`} readOnly />
        <NumberField label="exposure_us" value={cap.exposure_us} step={100} min={0} onChange={(v) => upd((c) => { c.capture.exposure_us = n(v) })} />
        <NumberField label="gain" value={cap.gain} step={0.05} min={0} onChange={(v) => upd((c) => { c.capture.gain = n(v) })} />
        <NumberField label="lens_position" value={cap.lens_position} step={0.01} min={0} onChange={(v) => upd((c) => { c.capture.lens_position = n(v) })} />
        <div className="grid grid-cols-2 gap-2">
          <NumberField label="colour R" value={cap.colour_gains[0]} step={0.01} min={0} onChange={(v) => upd((c) => { c.capture.colour_gains[0] = n(v) })} />
          <NumberField label="colour B" value={cap.colour_gains[1]} step={0.01} min={0} onChange={(v) => upd((c) => { c.capture.colour_gains[1] = n(v) })} />
        </div>
      </Section>
      <Section title={T.layout}>
        <NumberField label="cols" value={layout.cols} step={1} min={1} onChange={(v) => upd((c) => { c.layout.cols = n(v) })} />
        <NumberField label="rows" value={layout.rows} step={1} min={1} onChange={(v) => upd((c) => { c.layout.rows = n(v) })} />
        <NumberField label="pot_cm" value={layout.pot_cm} unit="cm" step={0.5} min={0} onChange={(v) => upd((c) => { c.layout.pot_cm = n(v) })} />
        <NumberField label="gap_cm" value={layout.gap_cm} unit="cm" step={0.5} min={0} onChange={(v) => upd((c) => { c.layout.gap_cm = n(v) })} />
      </Section>
      <Section title={T.qc} cols={5}>
        <NumberField label="px_per_cm_ref" value={qc.px_per_cm_ref} step={0.1} min={0} onChange={(v) => upd((c) => { c.qc.px_per_cm_ref = n(v) })} />
        <NumberField label="edge_tol" value={qc.edge_tol} step={0.005} min={0} onChange={(v) => upd((c) => { c.qc.edge_tol = n(v) })} />
        <NumberField label="drift_warn_px" value={qc.drift_warn_px} step={1} min={0} onChange={(v) => upd((c) => { c.qc.drift_warn_px = n(v) })} />
        <NumberField label="drift_fail_px" value={qc.drift_fail_px} step={1} min={0} onChange={(v) => upd((c) => { c.qc.drift_fail_px = n(v) })} />
        <NumberField label="drift_resp_min" value={qc.drift_resp_min} step={0.01} min={0} onChange={(v) => upd((c) => { c.qc.drift_resp_min = n(v) })} />
      </Section>
      <Section title={T.analysis} cols={5}>
        <NumberField label="tol_pp" value={analysis.tol_pp} step={0.1} min={0} onChange={(v) => upd((c) => { c.analysis.tol_pp = n(v) })} />
        <NumberField label="sep_ratio" value={analysis.sep_ratio} step={0.1} min={0} onChange={(v) => upd((c) => { c.analysis.sep_ratio = n(v) })} />
        <NumberField label="hist_bins" value={analysis.hist_bins} step={1} min={4} onChange={(v) => upd((c) => { c.analysis.hist_bins = n(v) })} />
        <NumberField label="soil_days" value={analysis.soil_days} step={1} min={1} onChange={(v) => upd((c) => { c.analysis.soil_days = n(v) })} />
        <SelectField label="dummy_fill" value={analysis.dummy_fill} options={DUMMY} onChange={(v) => upd((c) => { c.analysis.dummy_fill = v })} />
      </Section>
      <Section title={T.led} cols={3}>
        <ToggleField label="enabled" checked={led.enabled} onChange={(v) => upd((c) => { c.led.enabled = v })} />
        <SelectField label="driver" value={(DRIVERS as readonly string[]).includes(led.driver) ? (led.driver as (typeof DRIVERS)[number]) : 'noop'} options={DRIVERS} onChange={(v) => upd((c) => { c.led.driver = v })} />
        <NumberField label="pin" value={led.pin} step={1} min={0} onChange={(v) => upd((c) => { c.led.pin = n(v) })} />
        <ToggleField label="active_high" checked={led.active_high} onChange={(v) => upd((c) => { c.led.active_high = v })} />
        <NumberField label="warmup_s" value={led.warmup_s} unit="s" step={10} min={0} onChange={(v) => upd((c) => { c.led.warmup_s = n(v) })} />
        <NumberField label="max_on_s" value={led.max_on_s} unit="s" step={60} min={0} onChange={(v) => upd((c) => { c.led.max_on_s = n(v) })} />
      </Section>
      <Section title={T.schedule} cols={3}>
        <TextField label="dawn (HH:MM)" value={schedule.dawn} placeholder="05:50" onChange={(v) => upd((c) => { c.schedule.dawn = v })} />
        <TextField label="pm (HH:MM)" value={schedule.pm} placeholder="15:00" onChange={(v) => upd((c) => { c.schedule.pm = v })} />
        <TextField label={T.tz} value={draft.tz} placeholder="Asia/Seoul" onChange={(v) => upd((c) => { c.tz = v })} />
      </Section>
      <Section title={T.mqtt} cols={3}>
        <TextField label="host" value={mqtt.host} onChange={(v) => upd((c) => { c.mqtt.host = v })} />
        <NumberField label="port" value={mqtt.port} step={1} min={1} max={65535} onChange={(v) => upd((c) => { c.mqtt.port = n(v) })} />
        <TextField label="growth_topic" value={mqtt.growth_topic} onChange={(v) => upd((c) => { c.mqtt.growth_topic = v })} />
      </Section>
      <Section title={T.rois} cols={2}>
        <div className="sm:col-span-2">
          <div className="mb-2 text-[12px] text-muted">
            {T.treatMode}: <b className="num text-ink">{draft.treat_mode || S.config.modeNone}</b>
            {draft.run_started && <span className="num"> · run_started {draft.run_started}</span>}
          </div>
          {draft.rois.length === 0 ? (
            <div className="text-[12px] text-faint">{ko.common.none}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead><tr>{S.config.roiCols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>
                  {draft.rois.map((r) => (
                    <tr key={r.plant_id}><td>{r.plant_id}</td><td>{r.treat || ko.common.dash}</td><td>{r.x}</td><td>{r.y}</td><td>{r.w}</td><td>{r.h}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Section>
    </div>
  )
}
