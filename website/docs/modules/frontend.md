---
sidebar_position: 2
---

# frontend

`frontend/` is the Web UI — a React 19 + TypeScript single-page
application built with Vite, using shadcn/ui (Radix primitives) +
Tailwind CSS v4. It's the third framework this module has been built in
(Angular, then Vue 3 + PrimeVue, now React), each rewrite keeping the same
route paths and the same backend API contract so it's a different stack
on top of the same product, not a redesign.

This page is about how the SPA itself is built — for what you can *do*
with it, see [Usage](../usage/single-models).

## Stack

React 19, TypeScript, Vite, `react-router-dom` v7 (classic
`<BrowserRouter>`/`<Routes>`, not the v7 data-router APIs),
`@tanstack/react-table` v8, `recharts` + shadcn's `chart.tsx` wrapper,
`monaco-editor` pinned to exactly `0.50.0`, `sonner` for toasts, and
Vitest + React Testing Library for tests. Package management is pnpm —
the only module in the repository that isn't a `uv` Python project or a
plain Docusaurus pnpm setup managed separately.

## Layout

| Path | Purpose |
|---|---|
| `src/api.ts` | The REST client — plain `fetch` wrappers over every backend endpoint, framework-free (no React import). |
| `src/types.ts` | TypeScript types for the API payload shapes. |
| `src/logic/*.ts` | `deployment.ts`, `visualization.ts`, `plot.ts`, `format.ts` — pure business-logic functions (payload building, chart-data shaping, metrics-table formatting) with no UI dependency. These carry their own `.test.ts` files, and are the majority of this project's test suite. |
| `src/env.ts`, `src/ws.ts` | Runtime config (`window.env`) and the visualization WebSocket client — also framework-free. |
| `src/theme.ts` | Light/dark theme handling via a `dark` class + CSS variables, using `useSyncExternalStore` for the theme subscription. |
| `src/notify.ts` | Thin wrapper around `sonner`'s `toast`. |
| `src/hooks/useConfirm.tsx` | An imperative confirm-dialog hook (`confirm({header, message, accept})`) backed by shadcn's `AlertDialog`. Every view that needs a confirmation renders `{dialog}` in its own tree — there's no single app-wide dialog singleton. |
| `src/components/DataTable.tsx` | The generic sortable/filterable/paginated table shared by every list view (`ModelList`, `InferenceList`, `DatasourceList`, `IoTDeviceList`, `ResultList`), built on `@tanstack/react-table`. |
| `src/components/MultiSelect.tsx` | Hand-rolled multi-select (trigger + popover + checkbox list, chip-style selected display) — used for model selection in configurations, device selection for IoT inference, metric pickers, and the results-to-compare picker. |
| `src/components/MetricsTable.tsx` | Renders one training result's train/val/test metric rows, extracted so both `ResultList`'s metrics dialog and `ResultCompareView`'s summary cards share it. |
| `src/components/CodeEditor.tsx` | A hand-rolled Monaco wrapper (`useEffect`-based create/dispose/watch lifecycle, not `@monaco-editor/react`), lazily `import()`ed only when a view mounts it — Monaco never lands in the app's main JS chunk. |
| `src/monacoEnvironment.ts` | Monaco worker wiring plus Python/Lua/Berry language registration (not the full 40+-language bundle). |
| `src/berryLanguage.ts` | A hand-written Monaco Monarch tokenizer for Tasmota's Berry scripting language (used by the IoT-inference Berry-script field) — Monaco ships no built-in Berry grammar, so this was authored directly from Berry's own Pygments lexer and EBNF grammar. |
| `src/components/Layout.tsx` | Sidebar + topbar shell around `<Outlet/>`; desktop keeps the sidebar always visible, mobile uses a shadcn `Sheet` slide-over. |
| `src/routes.tsx` | The route table — one `React.lazy`-imported view per route, for per-route code splitting. |
| `src/views/*.tsx` | One file per screen (`ModelList`, `ModelView`, `ConfigurationView`, `DeploymentList`, `ResultList`, `ResultCompareView`, `PlotView`, `InferenceList`, `InferenceIoTView`, `DatasourceList`, `IoTDeviceList`, etc.). |

## How it talks to the backend

Every view fetches data through hand-rolled `useEffect`s calling
functions in `src/api.ts` — there is no data-fetching library
(`@tanstack/react-query` was installed at one point, found to be
completely unused including its `QueryClientProvider` wrapper in
`main.tsx`, and removed). `src/api.ts` and `src/types.ts` encode the real
wire contract, including several details that aren't obvious from the
backend's own field names alone:

- Model create/edit executes the submitted code server-side (via the
  matching `mlcode_executor`); a TensorFlow model must call
  `model.compile(...)` or the executor rejects it.
- IoT-device inference deploy (`POST /results/inference-iot/{id}`) expects
  `code`, `device_token` (an array), `model_result`, `applyIntQuant`.
- Federated deploy payloads use the field name `agg_strategy`, not
  `strategy`.
- Deployment payloads must omit optional empty fields entirely — see
  `buildDeploymentPayload()` in `src/logic/deployment.ts`.
- Trained-model download (`GET /results/model/{id}`) returns a raw blob;
  the file extension to use comes from the response's `ML-Framework`
  header, not the URL.
- Chart data (`GET /results/chart/{id}`) returns
  `{metrics: [{name, series: [{name, value}]}], conf_mat}`; metric names
  ending in `_val` are hidden from the metric-picker UI but still plotted
  when their base (non-`_val`) metric is selected.
- The visualization WebSocket connects to `<baseUrl>/ws/`, then sends
  `{"topic": "...", "classification": true|false}` once open — matching
  `backend/app/websocket.py`'s relay (see the
  [backend page](./backend)).

## The Monaco code editor

`CodeEditor.tsx` deliberately does not use `@monaco-editor/react`, even
though it's the default pairing for React + Monaco. That package wants to
own the Monaco import/loader lifecycle itself (CDN-by-default, or its own
bundling path), which conflicts with importing only
`monaco-editor/esm/vs/editor/editor.api` plus specific per-language
contribution modules — the approach that keeps the editor's own JS chunk
in the hundreds-of-KB range instead of pulling in every bundled language
and the full TS/CSS/HTML/JSON language services. `CodeEditor.tsx` instead
hand-rolls the same ref-based create/dispose/watch-props lifecycle using
`useEffect`s. `monaco-editor` is pinned to exactly `0.50.0` because
`0.56.0` restructured `basic-languages/` away from the
per-language-directory layout `monacoEnvironment.ts`'s imports depend on.

## Testing

```bash
pnpm test:run     # Vitest + React Testing Library
pnpm typecheck    # tsc -b --noEmit
pnpm build        # tsc -b && vite build
pnpm test:e2e     # Playwright, real browser, mocked /api/*
```

Unit tests are mostly the ported `src/logic/*.test.ts` files plus
`api.test.ts`/`ws.test.ts`, a `routes.test.ts` smoke test that every view
module resolves without throwing, and component-level tests for
individual views. A separate Playwright E2E suite
(`e2e/golden-path.spec.ts`) drives the real app — real routing, real
forms, the real Monaco editor — through create-model → create-configuration
→ deploy → simulate a finished training result → view metrics → deploy
for inference. Every `/api/*` call in the E2E suite is intercepted and
answered by `e2e/mock-backend.ts`, a small stateful fake backend sharing
the test process's JS heap, since a real Kubernetes-backed training run
isn't something CI can do.

## Deployment

`Dockerfile`, `nginx-custom.conf`, `start.sh`, and `public/env.template.js`
implement the same runtime-configuration contract the app has always
used: an nginx `/api` reverse proxy (with WebSocket upgrade handling) in
front of the backend, and a `window.env` object populated at container
start from `BACKEND_URL`/`BACKEND_PROXY_URL`/`ENABLE_FEDML_BLOCKCHAIN`
environment variables — the same variables `kustomize` sets, so
Kubernetes manifests don't need framework-specific changes.

## See also

- [backend](./backend) — the API this SPA talks to exclusively over
  HTTP/WebSocket; see its "Talking to `mlcode_executor`" and `/ws/`
  sections for the server side of the contracts above.
- [kafkaml-client](./kafkaml-client) — a Python SDK covering the same
  backend API as an alternative to this UI.
