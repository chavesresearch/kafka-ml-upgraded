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
