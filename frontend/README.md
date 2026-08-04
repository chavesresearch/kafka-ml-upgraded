# Kafka-ML Frontend (Vue 3 + TypeScript)

Vue 3 + TypeScript + Vite + PrimeVue rewrite of the original Angular 9 frontend
(`../frontend`). Same screens, same routes, same backend API — a fraction of
the size (~76 kB gzipped main bundle) and a maintained toolchain, with a
refreshed UI: a persistent sidebar shell, light/dark theming, and Monaco-editor
code fields for model definitions and Tasmota Berry scripts.

## Development

```bash
npm install
npm run dev            # http://localhost:5173
```

The dev server proxies `/api` (and the `/api/ws/` WebSocket) to the Kafka-ML
backend, rewriting the Host header to `localhost` so Django's ALLOWED_HOSTS
accepts it. Point it at another backend with:

```bash
KAFKAML_BACKEND=http://192.168.218.2:6135 npm run dev
```

## Build

```bash
npm run build          # vue-tsc --noEmit, then vite build; output in dist/
npm run typecheck      # type-check only, no build
```

## Tests

```bash
npm run test:run       # single run, used by CI
npm test               # watch mode
npm run test:coverage  # with coverage report
```

Unit tests for business logic live next to the code in `src/logic/*.test.ts`
(deployment payload building/validation, the live visualization state
machine, metric formatting, chart data building); `src/api.test.ts` and
`src/ws.test.ts` cover the backend client; a couple of `src/views/*.test.ts`
cover component wiring (data fetching, delete flows, form validation). See
`CLAUDE.md` for the testing conventions.

## UI

- **Theme**: light/dark toggle in the sidebar (persisted, and applied before
  first paint — no flash). Built on PrimeVue's Lara Light/Dark Indigo themes;
  custom styles read PrimeVue's CSS variables so they follow automatically.
- **Code fields**: model imports/code and Tasmota Berry scripts use a
  Monaco-editor component (`src/components/CodeEditor.vue`) instead of plain
  textareas — syntax highlighting, line numbers, matches the active theme.
  It's lazy-loaded per screen, not on the app's critical path.

## Docker

```bash
docker build --tag localhost:5000/frontend .
docker push localhost:5000/frontend
```

The image serves the app with nginx and keeps the same runtime contract as the
Angular image:

| Env var | Default | Purpose |
|---|---|---|
| `BACKEND_PROXY_URL` | `http://localhost:80` | Where nginx proxies `/api` and `/api/ws/` |
| `BACKEND_URL` | `/api` | Base URL the browser uses (written into `env.js`) |
| `ENABLE_FEDML_BLOCKCHAIN` | `0` | Set `1` to show the blockchain-traced training toggle |

Because the contract is unchanged, the existing `frontend-deployment.yaml` works
by only swapping the image name.

See `CLAUDE.md` for architecture notes, the theme system, the Monaco
lazy-loading setup, and backend contract details.
