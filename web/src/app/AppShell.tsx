import { Outlet, useLocation } from 'react-router-dom'
import { TopBar } from '@/components/layout/TopBar'
import { BottomTabBar } from '@/components/layout/BottomTabBar'
import { PageTransition } from '@/components/layout/PageTransition'
import { DummyBanner } from '@/components/ui/DummyBanner'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'

export function AppShell() {
  const { pathname } = useLocation()
  return (
    <div className="min-h-dvh flex flex-col bg-bg text-ink">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-md focus:bg-elev focus:px-3 focus:py-2">
        본문으로 건너뛰기
      </a>
      <TopBar />
      <main id="main" className="mx-auto w-full max-w-[1440px] flex-1 px-4 pb-24 pt-4 md:px-6 md:pb-10">
        <DummyBanner />
        <ErrorBoundary key={pathname}>
          <PageTransition pathname={pathname}>
            <Outlet />
          </PageTransition>
        </ErrorBoundary>
      </main>
      <BottomTabBar />
    </div>
  )
}
