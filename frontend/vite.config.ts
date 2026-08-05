/// <reference types="vitest/config" />
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev proxy targets the Kafka-ML backend. The backend only accepts hosts
// listed in ALLOWED_HOSTS, so the proxy rewrites the Host header to
// "localhost". Override the target with KAFKAML_BACKEND, e.g.:
//   KAFKAML_BACKEND=http://192.168.218.2:6135 npm run dev
const backend = process.env.KAFKAML_BACKEND || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api/ws': {
        target: backend,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        headers: { host: 'localhost' },
      },
      '/api': {
        target: backend,
        rewrite: (path) => path.replace(/^\/api/, ''),
        headers: { host: 'localhost' },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    // e2e/ holds Playwright specs (real browser, real Monaco, mocked
    // /api/* via route interception - see e2e/mock-backend.ts) - a
    // completely different test runner/API (`@playwright/test`, not
    // vitest's globals), picked up by `npx playwright test`, not this
    // suite. Vitest's default include glob (`**/*.{test,spec}.*`) would
    // otherwise also try to collect it and fail on the unrecognized API.
    // Setting `exclude` replaces vitest's own default list rather than
    // extending it, so it's repeated here in full plus `e2e/`.
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/cypress/**',
      '**/.{idea,git,cache,output,temp}/**',
      '**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*',
      '**/e2e/**',
    ],
    // Real monaco-editor needs a browser (Workers, canvas layout) and its
    // module-only package.json doesn't resolve under Vitest's SSR module
    // graph anyway — see src/test-mocks/monaco-editor.ts. Aliased by exact
    // specifier (not prefix): Vite's string alias replaces only the matched
    // portion and appends the rest of the specifier verbatim, so aliasing
    // the bare "monaco-editor" package name would turn ".../editor.api"
    // into a bogus path appended to the stub file.
    alias: {
      'monaco-editor/esm/vs/editor/editor.api': path.resolve(
        import.meta.dirname,
        './src/test-mocks/monaco-editor.ts',
      ),
    },
  },
})
