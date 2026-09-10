import type { ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { ko } from '@/i18n/ko'
import { AlertBanner } from './AlertBanner'
import { Button } from './Button'
import { Skeleton } from './Skeleton'

interface Props<T> {
  data: T | undefined
  isPending: boolean
  error: unknown
  refetch?: () => void
  skeleton?: ReactNode
  children: (data: T) => ReactNode
}

export function QueryState<T>({ data, isPending, error, refetch, skeleton, children }: Props<T>) {
  if (data !== undefined) return <>{children(data)}</>
  if (isPending) return <>{skeleton ?? <Skeleton className="h-40" />}</>
  const msg = error instanceof ApiError ? `${error.code}: ${error.message}` : error instanceof Error ? error.message : String(error ?? '')
  return (
    <AlertBanner level="bad" title={ko.common.error}>
      <div className="num text-[12px]">{msg}</div>
      {refetch && <Button variant="ghost" size="sm" className="mt-2" onClick={refetch}>{ko.common.retry}</Button>}
    </AlertBanner>
  )
}
