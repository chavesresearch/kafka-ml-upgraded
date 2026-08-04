// Light/dark theme switching. Tailwind v4 + shadcn theme entirely via a
// `dark` class on <html> and CSS variables (no separate stylesheet swap
// needed, unlike the old PrimeVue-based frontend). An inline boot script in
// index.html applies the stored choice before first paint, so there is no
// flash of the wrong theme.
import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'kafkaml-theme'

const listeners = new Set<() => void>()

function getSnapshot(): boolean {
  return typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback)
  return () => listeners.delete(callback)
}

export function setTheme(dark: boolean): void {
  document.documentElement.classList.toggle('dark', dark)
  try {
    localStorage.setItem(STORAGE_KEY, dark ? 'dark' : 'light')
  } catch {
    // Private browsing / storage disabled: theme just won't persist.
  }
  listeners.forEach((l) => l())
}

export function useTheme() {
  const isDark = useSyncExternalStore(subscribe, getSnapshot, () => false)
  return { isDark, toggle: () => setTheme(!isDark) }
}
