// Runtime environment, injected via public/env.js (window.env).
// Mirrors the Angular environment.prod.ts pattern.
interface RuntimeEnv {
  API_SERVER_URL?: string
  ENABLE_FEDML_BLOCKCHAIN?: string
}

const env: RuntimeEnv =
  (typeof window !== 'undefined' ? (window as Window & { env?: RuntimeEnv }).env : undefined) || {}

export const baseUrl: string = env.API_SERVER_URL || '/api'
export const enableFederatedBlockchain: boolean = env.ENABLE_FEDML_BLOCKCHAIN === '1'
