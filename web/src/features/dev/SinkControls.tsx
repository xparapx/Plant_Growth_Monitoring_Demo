import { Camera, Save } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Expander } from '@/components/ui/Expander'
import { KeyValue } from '@/components/ui/KeyValue'
import { LiveDot } from '@/components/ui/LiveDot'
import { Meter } from '@/components/ui/Meter'
import { NumberField } from '@/components/ui/NumberField'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Segmented } from '@/components/ui/Segmented'
import { Toggle } from '@/components/ui/Toggle'

const VARIANTS = ['primary', 'accent', 'ghost', 'sub'] as const
const SIZES = ['sm', 'md', 'lg'] as const

export function SinkControls() {
  const [seg, setSeg] = useState<'15m' | '1h' | '6h'>('1h')
  const [on, setOn] = useState(true)
  const [num, setNum] = useState<number | ''>(20000)
  const [busy, setBusy] = useState(false)
  return (
    <section id="controls" className="scroll-mt-20 flex flex-col gap-4">
      <Card animate={false}>
        <SectionHeader title="Button — variants × sizes · busy · icon · disabled" />
        <div className="flex flex-col gap-3">
          {SIZES.map((s) => (
            <div key={s} className="flex flex-wrap items-center gap-2">
              <span className="num w-8 text-[11px] text-muted">{s}</span>
              {VARIANTS.map((v) => <Button key={v} variant={v} size={s}>{v}</Button>)}
              <Button size={s} icon={<Camera size={15} />}>icon</Button>
              <Button size={s} disabled>disabled</Button>
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="accent" icon={<Save size={15} />} busy={busy} onClick={() => { setBusy(true); window.setTimeout(() => setBusy(false), 1500) }}>busy 1.5s</Button>
          </div>
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card animate={false}>
          <SectionHeader title="Segmented · Toggle" />
          <div className="flex flex-wrap items-center gap-4">
            <Segmented options={[{ value: '15m', label: '15m' }, { value: '1h', label: '1h' }, { value: '6h', label: '6h', disabled: true }]} value={seg} onChange={setSeg} ariaLabel="bucket" />
            <Segmented options={[{ value: '15m', label: '폼' }, { value: '1h', label: 'JSON' }, { value: '6h', label: 'sm' }]} value={seg} onChange={setSeg} size="sm" ariaLabel="bucket small" />
            <span className="flex items-center gap-2"><Toggle checked={on} onChange={setOn} label="LED enabled" /><span className="num text-[12px] text-muted">{String(on)}</span></span>
            <Toggle checked={false} onChange={() => undefined} label="disabled" disabled />
          </div>
        </Card>
        <Card animate={false}>
          <SectionHeader title="NumberField" />
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="exposure_us" value={num} onChange={setNum} step={100} min={0} />
            <NumberField label="pot_cm" value={15} onChange={() => undefined} unit="cm" step={0.5} />
          </div>
        </Card>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card animate={false}>
          <SectionHeader title="KeyValue — cols 3 · note" />
          <KeyValue cols={3} items={[{ k: 'hostname', v: 'plant-hub' }, { k: 'python', v: '3.11.2' }, { k: 'uptime', v: '3일 4시간', note: 'pid 4242' }, { k: 'data_dir', v: '/home/pi/plant/data/very/long/path/that/truncates' }, { k: 'opencv', v: '4.10.0' }, { k: 'tz', v: 'Asia/Seoul' }]} />
        </Card>
        <Card animate={false}>
          <SectionHeader title="Meter — default · warn · bad" />
          <div className="flex flex-col gap-3">
            <Meter value={38} max={100} label="disk 38%" />
            <Meter value={88} max={100} label="disk 88%" tone="warn" />
            <Meter value={97} max={100} label="disk 97%" tone="bad" />
          </div>
        </Card>
      </div>
      <Card animate={false}>
        <SectionHeader title="Expander · LiveDot" sub="Expander 본문은 첫 열림 때 렌더 (lazy)" actions={<LiveDot />} />
        <div className="flex flex-col gap-2">
          <Expander summary="상태 JSON (닫힘)"><pre className="num text-[11.5px]">{JSON.stringify({ state: 'open', driver: 'mock', clients: 1 }, null, 2)}</pre></Expander>
          <Expander summary="열려 있는 Expander" defaultOpen><p className="text-[12.5px] text-muted">defaultOpen=true 인 경우.</p></Expander>
        </div>
      </Card>
    </section>
  )
}
