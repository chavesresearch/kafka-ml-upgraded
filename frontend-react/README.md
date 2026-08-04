# Kafka-ML Frontend (React + TypeScript)

React 19 + TypeScript + Vite + shadcn/ui rewrite of `../frontend` (Vue 3),
itself a rewrite of the original Angular 9 frontend. Same screens, same
routes, same backend API — a different stack, not a different product.

Dependencies are managed with [pnpm](https://pnpm.io/), not npm.

## Development

```bash
pnpm install
pnpm dev               # http://localhost:5173
```

The dev server proxies `/api` (and the `/api/ws/` WebSocket) to the Kafka-ML
backend, rewriting the Host header to `localhost` so the backend's
ALLOWED_HOSTS accepts it. Point it at another backend with:

```bash
KAFKAML_BACKEND=http://192.168.218.2:6135 pnpm dev
```

## Build

```bash
pnpm build              # tsc -b, then vite build; output in dist/
pnpm typecheck           # type-check only, no build
```

## Tests

```bash
pnpm test:run            # single run, used by CI
pnpm test                # watch mode
```

Unit tests for business logic live next to the code in `src/logic/*.test.ts`
(deployment payload building/validation, the live visualization state
machine, metric formatting, chart data building) — ported unchanged from
the Vue app, since they were already framework-free. `src/api.test.ts` and
`src/ws.test.ts` cover the backend client; `routes.test.ts` and a couple of
`src/views/*.test.tsx` cover routing and component wiring. See `CLAUDE.md`
for the testing conventions and what was verified end-to-end against a
live backend.

## UI

- **Theme**: light/dark toggle in the sidebar (persisted, applied before
  first paint — no flash). shadcn/ui + Tailwind CSS v4, indigo accent to
  match the old PrimeVue Lara Indigo theme.
- **Code fields**: model imports/code and Tasmota Berry scripts use a
  Monaco-editor component (`src/components/CodeEditor.tsx`) instead of
  plain textareas — syntax highlighting, line numbers, matches the active
  theme. Lazy-loaded per screen, not on the app's critical path.

## Docker

```bash
docker build --tag localhost:5000/frontend .
docker push localhost:5000/frontend
```

The image serves the app with nginx and keeps the same runtime contract as
the Vue and Angular images before it:

| Env var | Default | Purpose |
|---|---|---|
| `BACKEND_PROXY_URL` | `http://localhost:80` | Where nginx proxies `/api` and `/api/ws/` |
| `BACKEND_URL` | `/api` | Base URL the browser uses (written into `env.js`) |
| `ENABLE_FEDML_BLOCKCHAIN` | `0` | Set `1` to show the blockchain-traced training toggle |

Because the contract is unchanged, the existing `frontend-deployment.yaml`
would work by only swapping the image name, if/when this gets cut over.

See `CLAUDE.md` for architecture notes, the stack's gotchas (monaco-editor
version pin, `@tanstack/react-table` version pin, the shadcn CLI alias
bug), and backend contract details.
