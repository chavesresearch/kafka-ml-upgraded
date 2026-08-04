import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import './index.css'
import App from './App.tsx'

// monacoEnvironment.ts is intentionally NOT imported here — it's pulled in
// lazily by CodeEditor.tsx so Monaco never lands in the app's main chunk.

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
        <Toaster position="bottom-center" richColors closeButton />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
)
