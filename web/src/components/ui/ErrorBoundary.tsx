import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertBanner } from './AlertBanner'

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('page error', error, info) }
  render() {
    if (this.state.error) {
      return (
        <AlertBanner level="bad" title="이 페이지를 그리는 중 오류가 났습니다">
          <pre className="num mt-1 whitespace-pre-wrap text-[11.5px]">{String(this.state.error.message)}</pre>
        </AlertBanner>
      )
    }
    return this.props.children
  }
}
