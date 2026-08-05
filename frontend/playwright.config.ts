import { defineConfig, devices } from '@playwright/test'

// Real click-through E2E tests, as distinct from vitest's unit/component
// suite (`pnpm test:run`) - see FUTURE.md's former "No end-to-end tests"
// entry and e2e/README.md for what this covers and why. No live backend
// or Kubernetes cluster involved: every /api/* call is intercepted and
// answered by e2e/mock-backend.ts's small stateful fake, the same
// approach kafkaml-client/tests takes for the same reason (a full
// cluster-backed E2E run isn't something CI can realistically do).
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:5183',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'pnpm run dev --port 5183 --strictPort',
    url: 'http://localhost:5183',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
