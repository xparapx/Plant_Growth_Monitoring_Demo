import { QueryClientProvider } from '@tanstack/react-query'
import { LazyMotion, MotionConfig, domAnimation } from 'motion/react'
import { RouterProvider } from 'react-router-dom'
import { queryClient } from '@/api/queries'
import { LiveEventsProvider } from '@/live/useLiveEvents'
import { ThemeProvider } from './theme'
import { router } from './router'

export function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <LiveEventsProvider>
          <LazyMotion features={domAnimation} strict>
            <MotionConfig reducedMotion="user">
              <RouterProvider router={router} />
            </MotionConfig>
          </LazyMotion>
        </LiveEventsProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
