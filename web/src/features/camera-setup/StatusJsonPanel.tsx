import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Expander } from '@/components/ui/Expander'
import { ko } from '@/i18n/ko'
import { useSetup } from './setupCtx'
import { ss } from './strings'

export function StatusJsonPanel() {
  const { status } = useSetup()
  const [copied, setCopied] = useState(false)
  const text = JSON.stringify(status, null, 2)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }
  return (
    <Expander summary={ko.setup.statusJson}>
      <div className="mb-2 flex justify-end">
        <Button variant="ghost" size="sm" onClick={copy} aria-label={ss.copy}>{copied ? ss.copied : ss.copy}</Button>
      </div>
      <pre className="num max-h-[360px] overflow-auto rounded-md bg-sunken p-3 text-[11px] leading-snug">{text}</pre>
    </Expander>
  )
}
