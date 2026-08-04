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

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-0.5 p-3">
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

  const currentLabel = navItems.find((item) => location.pathname.startsWith(item.to))?.label ?? 'Kafka-ML'

  return (
    <div className="grid min-h-svh md:grid-cols-[240px_1fr]">
      <aside className="sticky top-0 hidden h-svh flex-col border-r bg-sidebar text-sidebar-foreground md:flex">
        <div className="flex items-center gap-2.5 px-5 py-4">
          <span className="grid size-7 place-items-center rounded-md bg-gradient-to-br from-primary to-primary/70 text-sm font-extrabold text-primary-foreground">
            K
          </span>
          <span className="text-[1.05rem] font-bold tracking-tight">Kafka-ML</span>
        </div>
        <NavLinks />
        <div className="border-t p-3">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-muted-foreground"
            onClick={toggle}
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
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu className="size-4" />
          </Button>
          <span className="text-sm font-semibold">{currentLabel}</span>
          <span className="flex-1" />
          <ThemeToggleButton className="md:hidden" />
        </header>

        <main className="p-5">
          <Suspense fallback={<div className="text-sm text-muted-foreground">Loading…</div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetHeader>
            <SheetTitle>Kafka-ML</SheetTitle>
          </SheetHeader>
          <NavLinks onNavigate={() => setMobileNavOpen(false)} />
        </SheetContent>
      </Sheet>
    </div>
  )
}
