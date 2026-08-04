import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Dev proxy targets the Kafka-ML backend. The Django backend only accepts
// hosts listed in ALLOWED_HOSTS, so the proxy rewrites the Host header to
// "localhost". Override the target with KAFKAML_BACKEND, e.g.:
//   KAFKAML_BACKEND=http://192.168.218.2:6135 npm run dev
const backend = process.env.KAFKAML_BACKEND || 'http://192.168.218.2:6135'

export default defineConfig({
  plugins: [vue()],
  build: {
    // Monaco's editor.api chunk lands ~2.3 MB raw (~594 kB gzip) — large but
    // isolated: it's only fetched when a view with <CodeEditor> mounts, not
    // on the app's critical path. Raised so Vite's size-warning heuristic
    // stays useful for genuine regressions elsewhere instead of nagging here.
    chunkSizeWarningLimit: 2500
  },
  server: {
    proxy: {
      '/api/ws': {
        target: backend,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        headers: { host: 'localhost' }
      },
      '/api': {
        target: backend,
        rewrite: (path) => path.replace(/^\/api/, ''),
        headers: { host: 'localhost' }
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    // Real monaco-editor needs a browser (Workers, canvas layout) and its
    // module-only package.json doesn't resolve under Vitest's SSR module
    // graph anyway — see src/test-mocks/monaco-editor.ts. Aliased by exact
    // specifier (not prefix) since Vite's string alias replaces only the
    // matched portion and appends the rest of the specifier verbatim —
    // aliasing the bare "monaco-editor" package name would turn
    // ".../editor.api" into a bogus path appended to the stub file.
    alias: {
      'monaco-editor/esm/vs/editor/editor.api': fileURLToPath(
        new URL('./src/test-mocks/monaco-editor.ts', import.meta.url)
      )
    }
  }
})
