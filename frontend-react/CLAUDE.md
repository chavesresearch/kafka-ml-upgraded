# Kafka-ML React frontend — instructions for AI assistants

A full framework rewrite of `../frontend` (Vue 3 + PrimeVue, itself already
a rewrite of the original Angular app) into React 19 + TypeScript, using
shadcn/ui + Tailwind CSS v4. Same design philosophy as every other port in
this project: same route paths, same API contract, same field names — a
different stack, not a different product. `../frontend` is the reference
implementation for behavior; when in doubt what a screen should *do*, read
the matching view there.

**Status: functionally complete, not yet cut over.** `../frontend` (Vue)
is still what's actually deployed. This directory is a sibling built for
comparison, same pattern as every other `-upgraded`/rewrite directory this
project has gone through before its own cutover.

## Stack (do not swap pieces without being asked)

- React 19, TypeScript, Vite (same build tool the Vue app used)
- **pnpm, not npm** — the only module in this repo that does. `pnpm-lock.yaml`
  is the real lockfile; there's deliberately no `package-lock.json`. The
  Dockerfile installs pnpm itself (`npm install -g pnpm@11`) before using
  it, since the `node:20-alpine` base image only ships npm. `pnpm-workspace.yaml`
  is not a real workspace config here - it only holds pnpm 11's
  auto-generated `minimumReleaseAgeExclude` list (packages pnpm's
  supply-chain-safety "minimum release age" gate would otherwise block);
  keep it committed, don't delete it as unused.
- [shadcn/ui](https://ui.shadcn.com/) (`radix-nova` preset, Radix
  primitives) + Tailwind CSS v4 — CSS variables in `src/index.css`,
  indigo accent chosen to match the old PrimeVue `lara-indigo` theme's
  brand color, not shadcn's default neutral gray
- `react-router-dom` v7 (`<BrowserRouter>` + `<Routes>`, not the v7 data
  router APIs — kept close to how the Vue app's router worked)
- `@tanstack/react-table` **v8.21.3, deliberately not v9** — see Gotchas
- `@tanstack/react-query` — installed, available, but **not used yet**;
  every view still does its own `useEffect` + `useState` fetch, matching
  the Vue app's "no state library, each view fetches its own data"
  philosophy. Worth adopting per-view if a view's loading/error/refetch
  logic grows past what a plain `useEffect` handles cleanly.
- `recharts` + shadcn's `chart.tsx` wrapper (`ChartContainer`,
  `ChartTooltip`, etc.) — replaces `primevue/chart` (Chart.js). This is
  shadcn's own recommended charting pairing (they ship an official
  Recharts-based chart recipe), not an arbitrary choice.
- `reactflow` — **installed, not used anywhere yet.** The user's stack
  request listed it conditionally ("if visualizing Kafka topic
  producer→consumer pipelines"); no current view is actually a topology
  diagram (Visualization is a live metrics chart, not a pipeline graph),
  so it wasn't forced in. Worth revisiting if a real pipeline-topology
  view gets requested.
- `monaco-editor` **pinned to exactly `0.50.0`** — see Gotchas
- `sonner` (toast) — replaces PrimeVue's `Toast`/`useToast`
- Vitest + React Testing Library — replaces Vue Test Utils, same overall
  approach (mock `@/api`/`@/notify`, mount, assert)

## Layout

| Path | Purpose |
|---|---|
| `src/api.ts` | REST client — **byte-for-byte the same file** as the Vue app's, just re-pathed imports (`@/types` instead of `./types`). Zero framework dependency, ported unchanged. |
| `src/types.ts` | Same payload shapes as the Vue app — copied unchanged. |
| `src/logic/*.ts` | `deployment.ts`, `visualization.ts`, `plot.ts`, `format.ts` — **copied unchanged** from the Vue app, including their `.test.ts` files (60 of the 72 tests in this project are these ported-as-is tests). These were already framework-free pure functions in the Vue app for exactly this reason: portable business logic, independent of the UI layer. Don't let framework-specific code creep back into these files. |
| `src/env.ts`, `src/ws.ts` | Same — framework-free, copied unchanged. |
| `src/theme.ts` | Simplified vs. the Vue version: Tailwind v4 + shadcn theme entirely via a `dark` class + CSS variables, no separate PrimeVue stylesheet to swap (the Vue app had to physically swap a `<link>` `href` between two compiled theme CSS files; shadcn doesn't need that). Uses `useSyncExternalStore`, not a Vue `ref`. |
| `src/notify.ts` | Thin wrapper around `sonner`'s `toast`, same `{ok, error}` shape the Vue app's `useNotify()` had. |
| `src/hooks/useConfirm.tsx` | Replaces PrimeVue's imperative `useConfirm()` — same call shape (`confirm({header, message, accept})`), backed by shadcn's `AlertDialog` instead of a global singleton. Every view that needs it renders `{dialog}` somewhere in its own tree (no app-wide `<ConfirmDialog/>` singleton like the Vue app had). |
| `src/components/DataTable.tsx` | Generic sortable/filterable/paginated table shared by every list view (`ModelList`, `InferenceList`, `DatasourceList`, `IoTDeviceList`, `ResultList`) — mirrors the *one* PrimeVue `<DataTable>` component reused the same way throughout the Vue app. Built on `@tanstack/react-table`. |
| `src/components/MultiSelect.tsx` | Hand-rolled multi-select (trigger + popover + checkbox list) — shadcn/ui doesn't ship one. Used by `ConfigurationView` (`ml_models`), `InferenceIoTView` (`device_token`), `PlotView`/`VisualizationView`... actually just `PlotView` (metric picker). Not a `<select multiple>` — needs chip-style selected-item display to match the old UX. |
| `src/components/CodeEditor.tsx` | Hand-rolled Monaco wrapper (refs + `useEffect`, not `@monaco-editor/react` — deliberately not using that library, see Gotchas). Same lazy-loading contract as the Vue version: `monacoEnvironment.ts` + Monaco's core editor module are both loaded via a runtime `import()` inside a mount effect, never from `main.tsx`, so Monaco never lands in the app's main chunk. |
| `src/monacoEnvironment.ts` | Copied unchanged from the Vue app (framework-free side-effect module: worker wiring + python/lua language registration only, not the full 40+-language bundle). |
| `src/components/Layout.tsx` | Sidebar + topbar shell (`<Outlet/>`-based), replaces `App.vue`. Desktop sidebar always visible; mobile uses a shadcn `Sheet` slide-over instead of PrimeVue's `Sidebar`. |
| `src/routes.tsx` | Route table — same paths as the Vue router, each view `React.lazy`-imported for the same per-route code-splitting the Vue app had. |
| `src/views/*.tsx` | One file per screen, matching the Vue app's `src/views/*.vue` 1:1 by filename (minus the extension). |

## Gotchas learned the hard way (keep these)

1. **shadcn's CLI silently mis-resolved the `@/*` path alias the first
   time it ran**, writing every generated file under a literal
   `./@/components/ui/*` directory instead of `./src/components/ui/*` -
   even though its own "Validating import alias ✔" preflight check
   passed. Root cause: the alias was only declared in
   `tsconfig.app.json` (referenced from the root `tsconfig.json` via
   TS project references), and the CLI's tsconfig reader apparently
   doesn't follow `references` to find `paths`. Fixed by **also**
   declaring the same `paths` entry directly in the root
   `tsconfig.json`'s own `compilerOptions` (TypeScript itself ignores
   this, since the root file's `"files": []` applies to nothing, but
   it's there for any tool that reads the root file directly instead of
   following references). Confirmed fixed by successfully running
   `npx shadcn add chart` afterward and seeing it land in the right
   place. If any future `shadcn add` run creates a stray top-level `@`
   directory again, this is why - move the files, don't just delete and
   retry.
2. **`monaco-editor` is pinned to exactly `0.50.0`, not the current
   latest (`0.56.0`).** `0.56.0` restructured `esm/vs/basic-languages/`
   away from per-language directories (`basic-languages/python/
   python.contribution.js` etc. no longer exist - confirmed by listing
   the installed package's actual contents, not assumed from a
   changelog) into some consolidated form. `monacoEnvironment.ts`'s
   `import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'`-style
   imports depend on that per-language layout existing. `0.50.0` is the
   exact version `../frontend` (Vue) already uses successfully with
   this identical lazy-loading pattern, so pinning to it (via `npm
   install monaco-editor@0.50.0 --save-exact`) was the pragmatic fix
   over reverse-engineering 0.56.0's new structure. Bonus: this also
   happens to drop a `pnpm audit` `dompurify` advisory that comes in
   transitively via 0.56.0's dependency chain - not why it was pinned,
   but worth knowing if someone re-checks `pnpm audit` later and wonders
   why it's clean here specifically.
3. **`@tanstack/react-table` is pinned to `8.21.3`, not the current
   latest (`9.x`).** v9 is a from-scratch rewrite with a completely
   different API (feature-based `TableFeatures` generic constraints;
   no more free-standing `getCoreRowModel()`/`useReactTable()` functions
   in the shape every existing tutorial, the shadcn data-table recipe,
   and this file's own `DataTable.tsx` all assume). Confirmed by
   actually hitting the resulting type errors (`Type 'T' does not
   satisfy the constraint 'TableFeatures'`) before pinning back to the
   v8 line, not assumed from a version number alone. Re-evaluate v9 only
   as a deliberate, scoped migration - not as a side effect of a routine
   `pnpm update`.
4. **TypeScript's very-new `"exports"`-strict module resolution (this
   project runs TS ~6.0, newer than `../frontend`'s ~5.9) can't find
   `monaco-editor`'s deep-import subpaths at all**, even the ones that
   physically exist with real `.d.ts` content
   (`esm/vs/editor/editor.api.d.ts`, the two `basic-languages/{python,lua}/
   *.contribution.d.ts` files) - `monaco-editor`'s own `package.json`
   `exports` map only declares a `types` condition for its root `.`
   entry, not for the `./*` wildcard deep-import pattern this project
   (and the Vue app) both rely on. Vite/esbuild resolve the runtime
   `.js` for the same specifiers fine (bundlers respect the wildcard's
   plain JS mapping); this is purely a `tsc` type-resolution gap. Fixed
   with explicit `paths` entries in `tsconfig.app.json` pointing straight
   at the physical `.d.ts` files, bypassing `exports` resolution
   entirely for just those three specifiers. If `monaco-editor` ever
   ships a `types` condition on that wildcard, these path overrides
   become redundant (harmless to leave, but worth removing then).
5. **`@monaco-editor/react` was deliberately *not* used**, even though
   it's the obvious/default React+Monaco pairing. It wants to own the
   Monaco import/loader lifecycle itself (CDN by default, or its own
   `loader.config({monaco})` bundling path), which conflicts with this
   project's bundle-size-conscious core-only-import strategy
   (`monaco-editor/esm/vs/editor/editor.api`, not the bare
   `monaco-editor` package, which pulls in every language + full
   TS/CSS/HTML/JSON language services - several MB never used here).
   `CodeEditor.tsx` hand-rolls the same ref-based
   create/dispose/watch-props lifecycle `CodeEditor.vue` used, just
   expressed as `useEffect`s instead of Vue's `onMounted`/`watch`. This
   is more code than `<Editor/>` would have been, but keeps the exact
   bundle-size guarantee `../frontend/CLAUDE.md`'s "Code editor" section
   documents and tests for (confirmed: this app's `editor.api` chunk is
   579 kB gzipped after `pnpm build` - same order of magnitude as the
   Vue app's own documented ~594 kB figure, not the multi-MB full bundle
   `@monaco-editor/react`'s default CDN path would pull down).
6. **The Dockerfile must copy all three tsconfig files, not just
   `tsconfig.json`.** This project uses TS project references
   (`tsconfig.json` has `"files": []` + `"references"` to
   `tsconfig.app.json`/`tsconfig.node.json`, no `compilerOptions` of its
   own for the actual source). `pnpm build` runs `tsc -b`, which follows
   those references - copying only `tsconfig.json` into the build stage
   (the pattern the Vue app's Dockerfile uses, since it doesn't use
   project references) would fail the Docker build the moment `tsc -b`
   tries to resolve a reference to a file that was never copied in. Caught
   by actually building the image, not by inspection - `npm run build`
   run locally against the full source tree never exercises this, since
   every file is already present there regardless of what a Dockerfile's
   `COPY` list says.

## Backend contract gotchas (identical to the Vue app - not re-derived, ported as-is)

Same list as `../frontend/CLAUDE.md`'s own section - these are backend
wire-contract facts, not frontend-framework-specific, so they apply
unchanged here:

1. Model create/edit executes the code server-side (tf/pth executor); a
   TF model must call `model.compile(...)`.
2. IoT inference deploy (`POST /results/inference-iot/{id}`) expects keys
   `code`, `device_token` (array), `model_result`, `applyIntQuant`.
3. Federated deploy expects `agg_strategy` (not `strategy`).
4. Deployment payload must omit optional empty fields - see
   `buildDeploymentPayload()` in `src/logic/deployment.ts` (ported
   unchanged, same function, same tests).
5. Trained model download (`GET /results/model/{id}`) returns a blob; the
   file extension comes from the `ML-Framework` response header.
6. Chart data (`GET /results/chart/{id}`) returns
   `{metrics: [{name, series: [{name, value}]}], conf_mat}`; metric names
   ending in `_val` are hidden from the selector but plotted when their
   base metric is selected.
7. Visualization WebSocket: connect to `<baseUrl>/ws/`, then send
   `{"topic": "...", "classification": true|false}` once open.

## Runtime configuration / Docker (identical contract to the Vue app)

`Dockerfile`, `nginx-custom.conf`, `start.sh`, `public/env.template.js`
are **copied unchanged** from `../frontend` - same `BACKEND_URL`/
`BACKEND_PROXY_URL`/`ENABLE_FEDML_BLOCKCHAIN` env vars, same `/api` nginx
proxy + WebSocket upgrade handling, same `window.env` runtime-config
pattern. This means the k8s deployment YAML would need zero changes
beyond the image name if this ever gets cut over, same as every other
port in this project.

## Testing approach

```bash
pnpm test:run     # Vitest + React Testing Library, 72 tests
pnpm typecheck    # tsc -b --noEmit
pnpm build        # tsc -b && vite build (also typechecks)
```

72 tests total: 60 are the ported `src/logic/*.test.ts` +
`src/api.test.ts` + `src/ws.test.ts` files (unchanged from the Vue app,
proving the ported business logic still behaves identically), plus
`routes.test.ts` (every view module resolves without throwing - same
cheap regression net the Vue app's `router.test.ts` had) and two
component-level tests (`ModelList.test.tsx`, `ConfigurationView.test.tsx`
- same scenarios the Vue app's own two component tests covered,
translated to React Testing Library idioms).

**Real end-to-end verification performed, not just unit tests**: started
`pnpm dev` against the live local backend (`localhost:8000`, via this
same `/api` proxy pattern the Vue app's `vite.config.ts` uses -
`KAFKAML_BACKEND` env var overrides the target), then drove it with a
headless Playwright script (`npx playwright`, not committed as a
dependency - ad hoc verification only, same as `../frontend/CLAUDE.md`'s
own documented Playwright usage) through all 8 main views plus the model
create form and a dark-mode toggle. Confirmed: real data rendered from
the live backend (including leftover rows from this project's own
`integration-tests/` suite), zero browser console errors across every
page, Monaco editor renders correctly with syntax highlighting, dark mode
repaints correctly (indigo accent, proper contrast). Screenshots were not
committed (ad hoc verification artifacts, not a repeatable suite).

## Remaining work

1. **Feature-parity audit vs. the Vue app hasn't been done by a human
   yet** - same caveat `../frontend/CLAUDE.md`'s own FUTURE.md entry
   already documents for the Vue-vs-Angular rewrite before it. This
   rewrite was verified against the live backend end-to-end (see above)
   but not clicked through screen-by-screen by a person yet.
2. **No end-to-end/integration test suite** - same gap the Vue app has
   (`FUTURE.md`'s "No end-to-end tests" entry applies here too).
3. **`reactflow` is installed but unused** - see Stack section above.
4. **`@tanstack/react-query` is installed but unused** - every view still
   hand-rolls its own fetch effect. Low priority unless a view's
   load/error/refetch logic grows complex enough to justify it.
5. Cutover (rename this directory to `frontend`, retire the Vue
   `frontend/`) hasn't happened - not requested yet, and this project's
   own established pattern is to keep the new and old implementations
   side by side, verified, until a deliberate cutover pass (see how
   every other `-upgraded` directory in this repo was eventually
   renamed into place).
