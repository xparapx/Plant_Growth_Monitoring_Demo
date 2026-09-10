export function Skeleton({ className = '', lines }: { className?: string; lines?: number }) {
  if (lines) {
    return (
      <div className={`flex flex-col gap-2 ${className}`} aria-hidden="true">
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="skeleton h-3.5" style={{ width: `${90 - (i % 3) * 18}%` }} />
        ))}
      </div>
    )
  }
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

export function PageSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-12" aria-busy="true" aria-label="불러오는 중">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="card h-[110px] p-4 xl:col-span-2"><Skeleton lines={2} /></div>
      ))}
      <div className="card h-[280px] p-4 md:col-span-2 xl:col-span-12"><Skeleton className="h-full" /></div>
      <div className="card h-[240px] p-4 xl:col-span-7"><Skeleton className="h-full" /></div>
      <div className="card h-[240px] p-4 xl:col-span-5"><Skeleton className="h-full" /></div>
    </div>
  )
}
