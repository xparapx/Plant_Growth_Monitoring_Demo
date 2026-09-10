import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from './AppShell'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { OverviewPage } from '@/features/overview/OverviewPage'

const TreatmentPage = lazy(() => import('@/features/treatment/TreatmentPage'))
const GrowthPage = lazy(() => import('@/features/growth/GrowthPage'))
const CapturePage = lazy(() => import('@/features/capture/CapturePage'))
const CameraSetupPage = lazy(() => import('@/features/camera-setup/CameraSetupPage'))
const SystemPage = lazy(() => import('@/features/system/SystemPage'))
const KitchenSinkPage = lazy(() => import('@/features/dev/KitchenSinkPage'))

const L = (el: React.ReactNode) => <Suspense fallback={<PageSkeleton />}>{el}</Suspense>

export const router = createBrowserRouter(
  [
    {
      path: '/',
      element: <AppShell />,
      children: [
        { index: true, element: <Navigate to="/overview" replace /> },
        { path: 'overview', element: <OverviewPage /> },
        { path: 'treatment', element: L(<TreatmentPage />) },
        { path: 'growth', element: L(<GrowthPage />) },
        { path: 'camera', element: L(<CapturePage />) },
        { path: 'camera/setup', element: L(<CameraSetupPage />) },
        { path: 'system', element: L(<SystemPage />) },
        { path: 'dev/kitchen', element: L(<KitchenSinkPage />) },
        { path: '*', element: <Navigate to="/overview" replace /> },
      ],
    },
  ],
  { basename: import.meta.env.BASE_URL.replace(/\/$/, '') || '/' },
)
