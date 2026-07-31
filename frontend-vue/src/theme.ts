// Light/dark theme switching.
// The active PrimeVue theme is a static stylesheet linked from index.html
// (<link id="theme-css">, served from public/themes/, populated by the
// `sync-themes` npm script). Switching themes swaps that link's href and
// toggles the `dark` class on <html>, which the custom CSS and Monaco react to.
// An inline boot script in index.html applies the stored choice before first
// paint, so there is no flash of the wrong theme.
import { ref } from 'vue'

const STORAGE_KEY = 'kafkaml-theme'
const THEMES = {
  light: '/themes/lara-light-indigo/theme.css',
  dark: '/themes/lara-dark-indigo/theme.css'
}

const isDark = ref(
  typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
)

export function setTheme(dark: boolean): void {
  isDark.value = dark
  document.documentElement.classList.toggle('dark', dark)
  const link = document.getElementById('theme-css') as HTMLLinkElement | null
  if (link) link.href = dark ? THEMES.dark : THEMES.light
  try {
    localStorage.setItem(STORAGE_KEY, dark ? 'dark' : 'light')
  } catch {
    // Private browsing / storage disabled: theme just won't persist.
  }
}

export function useTheme() {
  return {
    isDark,
    toggle: () => setTheme(!isDark.value)
  }
}
