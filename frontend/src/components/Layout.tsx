import { Suspense, useState, type ComponentType } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Code2,
  Settings,
  ExternalLink,
  CheckSquare,
  RefreshCw,
  BookOpen,
  LineChart,
  Wifi,
  Menu,
  Sun,
  Moon,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { useTheme } from '@/theme'

interface NavItem {
  label: string
  to: string
  icon: ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  { label: 'Models', to: '/models', icon: Code2 },
  { label: 'Configurations', to: '/configurations', icon: Settings },
  { label: 'Deployments', to: '/deployments', icon: ExternalLink },
  { label: 'Training', to: '/results', icon: CheckSquare },
  { label: 'Inference', to: '/inferences', icon: RefreshCw },
  { label: 'Datasources', to: '/datasources', icon: BookOpen },
  { label: 'Visualization', to: '/visualization', icon: LineChart },
  { label: 'IoT Devices', to: '/devices', icon: Wifi },
]

// Create/edit/detail routes use singular, kebab-cased paths
// (/model-create, /model/:id, /deploy/:id, ...) that never match their
// section's plural nav path (/models) via a plain startsWith - so the
// topbar fell back to a generic "Kafka-ML" label on every form/detail
// screen, exactly where knowing which section you're in matters most.
// Checked most-specific-first.
const sectionPatterns: { prefix: string; label: string }[] = [
  { prefix: '/results/inference-iot/', label: 'Inference' },
  { prefix: '/results/inference/', label: 'Inference' },
  { prefix: '/results/chart/', label: 'Training' },
  { prefix: '/results', label: 'Training' },
  { prefix: '/model-create', label: 'Models' },
  { prefix: '/model/', label: 'Models' },
  { prefix: '/models', label: 'Models' },
  { prefix: '/configuration-create', label: 'Configurations' },
  { prefix: '/configuration/', label: 'Configurations' },
  { prefix: '/configurations', label: 'Configurations' },
  { prefix: '/deploy/', label: 'Configurations' },
  { prefix: '/deployments', label: 'Deployments' },
  { prefix: '/inferences', label: 'Inference' },
  { prefix: '/datasources', label: 'Datasources' },
  { prefix: '/visualization', label: 'Visualization' },
  { prefix: '/devices-create', label: 'IoT Devices' },
  { prefix: '/device/', label: 'IoT Devices' },
  { prefix: '/devices', label: 'IoT Devices' },
]

function sectionLabelFor(pathname: string): string {
  return sectionPatterns.find((p) => pathname.startsWith(p.prefix))?.label ?? 'Kafka-ML'
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main navigation" className="flex flex-1 flex-col gap-0.5 p-3">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors',
              'hover:bg-accent hover:text-accent-foreground',
              isActive && 'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground',
            )
          }
        >
          <item.icon className="size-4 shrink-0" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

function ThemeToggleButton({ className }: { className?: string }) {
  const { isDark, toggle } = useTheme()
  return (
    <Button
      variant="ghost"
      size="icon"
      className={className}
      onClick={toggle}
      aria-label="Toggle theme"
      aria-pressed={isDark}
      title={isDark ? 'Switch to light' : 'Switch to dark'}
    >
      {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  )
}

export default function Layout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const location = useLocation()
  const { isDark, toggle } = useTheme()

  const currentLabel = sectionLabelFor(location.pathname)

  return (
    <div className="grid min-h-svh md:grid-cols-[240px_1fr]">
      <a
        href="#main-content"
        className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:top-3 focus-visible:left-3 focus-visible:z-50 focus-visible:rounded-md focus-visible:bg-primary focus-visible:px-4 focus-visible:py-2 focus-visible:text-sm focus-visible:font-medium focus-visible:text-primary-foreground"
      >
        Skip to main content
      </a>
      <aside className="sticky top-0 hidden h-svh flex-col border-r bg-sidebar text-sidebar-foreground md:flex">
        <div className="flex items-center gap-2.5 px-5 py-4">
          <img src="/favicon.svg" alt="" className="size-7 shrink-0" />
          <span className="text-[1.05rem] font-bold tracking-tight">Kafka-ML</span>
        </div>
        <NavLinks />
        <div className="border-t p-3">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-muted-foreground"
            onClick={toggle}
            aria-pressed={isDark}
          >
            {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            {isDark ? 'Light mode' : 'Dark mode'}
          </Button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b bg-background/90 px-5 backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Menu"
            aria-expanded={mobileNavOpen}
            aria-controls="mobile-nav"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu className="size-4" />
          </Button>
          <span className="text-sm font-semibold">{currentLabel}</span>
          <span className="flex-1" />
          <ThemeToggleButton className="md:hidden" />
        </header>

        {/* tabIndex=-1: <main> isn't natively focusable, so without it the skip
            link above only scrolls the viewport here - keyboard focus stays on
            <body> and the very next Tab restarts from the top of the page. */}
        <main id="main-content" tabIndex={-1} className="p-5 focus:outline-none">
          <Suspense fallback={<div className="text-sm text-muted-foreground">Loading…</div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent id="mobile-nav" side="left" className="w-64 p-0">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2.5">
              <img src="/favicon.svg" alt="" className="size-6 shrink-0" />
              Kafka-ML
            </SheetTitle>
          </SheetHeader>
          <NavLinks onNavigate={() => setMobileNavOpen(false)} />
        </SheetContent>
      </Sheet>
    </div>
  )
}
