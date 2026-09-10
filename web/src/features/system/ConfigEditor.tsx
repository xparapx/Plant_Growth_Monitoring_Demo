import type { UseQueryResult } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '@/api/client'
import { useConfigSave } from '@/api/mutations'
import type { ConfigDoc, PlantConfig } from '@/api/types'
import { AlertBanner, type AlertLevel } from '@/components/ui/AlertBanner'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Segmented } from '@/components/ui/Segmented'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { ConfigForm } from './ConfigForm'
import { changedSections, parseConfigJson, pickSections } from './configDiff'
import { S } from './strings'

type Tab = 'form' | 'json'
const TABS: { value: Tab; label: string }[] = [{ value: 'form', label: S.config.form }, { value: 'json', label: S.config.json }]

export function ConfigEditor({ q }: { q: UseQueryResult<ConfigDoc> }) {
  return (
    <Card className="md:col-span-2 xl:col-span-12">
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton className="h-64" />}>
        {(doc) => <Editor doc={doc} refetch={() => q.refetch()} />}
      </QueryState>
    </Card>
  )
}

function Editor({ doc, refetch }: { doc: ConfigDoc; refetch: () => void }) {
  const save = useConfigSave()
  const [tab, setTab] = useState<Tab>('form')
  const [draft, setDraft] = useState<PlantConfig>(() => structuredClone(doc.config))
  const [jsonText, setJsonText] = useState('')
  const [jsonErr, setJsonErr] = useState<string | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [banner, setBanner] = useState<{ level: AlertLevel; text: string } | null>(null)

  useEffect(() => {                               // a new mtime (save, WS config.changed) resets the draft
    setDraft(structuredClone(doc.config))
    setJsonText(JSON.stringify(doc.config, null, 2))
    setJsonErr(null)
  }, [doc.mtime, doc.config])

  const changed = useMemo(() => changedSections(doc.config, draft), [doc.config, draft])

  const switchTab = (t: Tab) => {
    if (t === 'json') { setJsonText(JSON.stringify(draft, null, 2)); setJsonErr(null) }
    setTab(t)
  }
  const onJson = (text: string) => {
    setJsonText(text)
    const r = parseConfigJson(text)
    if (r.ok) { setDraft(r.value); setJsonErr(null) } else setJsonErr(r.error)
  }
  const reset = () => { setDraft(structuredClone(doc.config)); setJsonText(JSON.stringify(doc.config, null, 2)); setJsonErr(null); setBanner(null) }
  const askSave = () => {
    if (jsonErr) return
    if (!changed.length) { setBanner({ level: 'info', text: S.config.noChange }); return }
    setConfirm(true)
  }
  const doSave = () => {
    save.mutate({ patch: pickSections(draft, changed), mtime: doc.mtime }, {
      onSuccess: () => { setConfirm(false); setBanner({ level: 'ok', text: `${S.config.saved} — ${ko.system.changed(changed)}` }) },
      onError: (e) => {
        setConfirm(false)
        if (e instanceof ApiError && e.status === 409) setBanner({ level: 'bad', text: S.config.stale })
        else if (e instanceof ApiError && e.status === 422) setBanner({ level: 'bad', text: e.message })
        else setBanner({ level: 'bad', text: e instanceof Error ? e.message : String(e) })
      },
    })
  }

  return (
    <>
      <SectionHeader
        title={ko.system.config}
        sub={<span className="num">{doc.path} · mtime {doc.mtime}</span>}
        actions={
          <>
            <Segmented options={TABS} value={tab} onChange={switchTab} size="sm" ariaLabel={ko.system.config} />
            <Button variant="ghost" size="sm" onClick={reset} disabled={!changed.length && !jsonErr}>{S.config.reset}</Button>
            <Button size="sm" onClick={askSave} disabled={Boolean(jsonErr) || !changed.length} busy={save.isPending}>{ko.system.save}{changed.length ? ` (${changed.length})` : ''}</Button>
          </>
        }
      />
      <div className="mb-3 flex flex-col gap-2">
        {doc.warnings.length > 0 && <AlertBanner level="warn" title={S.config.warnings}><ul className="num list-disc pl-4 text-[12px]">{doc.warnings.map((w) => <li key={w}>{w}</li>)}</ul></AlertBanner>}
        {doc.check.bad.length > 0 && <AlertBanner level="bad" title={S.config.checkBad}><ul className="list-disc pl-4">{doc.check.bad.map((w) => <li key={w}>{w}</li>)}</ul></AlertBanner>}
        {doc.check.warn.length > 0 && <AlertBanner level="warn" title={S.config.checkWarn}><ul className="list-disc pl-4">{doc.check.warn.map((w) => <li key={w}>{w}</li>)}</ul></AlertBanner>}
        {banner && (
          <AlertBanner level={banner.level} dismissible>
            {banner.text}
            {banner.level === 'bad' && banner.text === S.config.stale && <Button variant="ghost" size="sm" className="ml-3" onClick={() => { setBanner(null); refetch() }}>{ko.common.retry}</Button>}
          </AlertBanner>
        )}
      </div>
      {tab === 'form' ? (
        <ConfigForm draft={draft} onChange={setDraft} />
      ) : (
        <div className="flex flex-col gap-2">
          <textarea
            className="num min-h-[420px] w-full resize-y rounded-md border border-border-soft bg-elev p-3 text-[12.5px] leading-relaxed text-ink outline-none focus:border-primary"
            value={jsonText}
            onChange={(e) => onJson(e.target.value)}
            spellCheck={false}
            aria-label="config.json"
            aria-invalid={Boolean(jsonErr)}
          />
          {jsonErr && <AlertBanner level="bad">{S.config.jsonBad(jsonErr)}</AlertBanner>}
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        title={S.config.confirmTitle}
        body={<><p>{S.config.confirmBody}</p><p className="num mt-2 font-semibold text-ink">{ko.system.changed(changed)}</p></>}
        confirmLabel={ko.system.save}
        busy={save.isPending}
        onConfirm={doSave}
        onCancel={() => setConfirm(false)}
      />
    </>
  )
}
