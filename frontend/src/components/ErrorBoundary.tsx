import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

// React has no hook equivalent for catching render errors - this must be a
// class component (getDerivedStateFromError/componentDidCatch). Layout.tsx
// wraps <Outlet/> in one keyed by the current pathname, so an unguarded
// throw from a single broken view (e.g. an unexpected API payload shape in
// a list-view cell renderer) only takes down that view instead of
// unmounting the whole app - React 19 unmounts the entire tree on an
// uncaught render error otherwise, with no boundary anywhere to stop it.
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled error rendering view:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <Card className="mx-auto mt-8 max-w-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="size-5 text-destructive" />
              Something went wrong
            </CardTitle>
            <CardDescription>
              This page hit an unexpected error and couldn't render. Try reloading, or go back and
              try again.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="rounded-md bg-muted p-3 font-mono text-xs break-all text-muted-foreground">
              {this.state.error.message}
            </p>
            <Button onClick={() => window.location.reload()}>Reload page</Button>
          </CardContent>
        </Card>
      )
    }

    return this.props.children
  }
}
