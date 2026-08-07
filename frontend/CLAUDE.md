# Kafka-ML React frontend — instructions for AI assistants

This is a full framework rewrite of the project's second-generation
frontend (Vue 3 + PrimeVue, itself a rewrite of the original Angular app)
into React 19 + TypeScript, using shadcn/ui + Tailwind CSS v4. Same design
philosophy as every other port in this project: same route paths, same API
contract, same field names — a different stack, not a different product.

**Status: this is the deployed frontend**, cut over 2026-08-04. It was
built as a sibling directory (`frontend-react/`), verified end-to-end
against the live backend, then renamed into `frontend/`'s place — same
pattern every other rewrite in this repo went through. The Vue
implementation that used to live at this path has been deleted outright
(not preserved anywhere, unlike the Angular/Django originals this whole
project rewrote, which still live on in the separate `../kafka-ml`
checkout) — the "Vue app" comparisons throughout this file describe code
that no longer exists in this tree, kept only because they explain *why*
something here is shaped the way it is. If you need to see the actual Vue
source, it's in git history before the cutover commit, not on disk.

## Stack (do not swap pieces without being asked)

- React 19, TypeScript, Vite (same build tool the Vue app used)
- **pnpm, not npm** — the only module in this repo that does. `pnpm-lock.yaml`
  is the real lockfile; there's deliberately no `package-lock.json`. The
  Dockerfile installs pnpm itself (`npm install -g pnpm@11`) before using
  it, on a `node:22-alpine` base image (pnpm 11 requires Node ≥22.13).
  `pnpm-workspace.yaml` is not a real workspace config here - it only holds
  pnpm 11's auto-generated `minimumReleaseAgeExclude` list (packages
  pnpm's supply-chain-safety "minimum release age" gate would otherwise
  block); keep it committed, don't delete it as unused.
- [shadcn/ui](https://ui.shadcn.com/) (`radix-nova` preset, Radix
  primitives) + Tailwind CSS v4 — CSS variables in `src/index.css`,
  indigo accent chosen to match the old PrimeVue `lara-indigo` theme's
  brand color, not shadcn's default neutral gray
- `react-router-dom` v7 (`<BrowserRouter>` + `<Routes>`, not the v7 data
  router APIs — kept close to how the Vue app's router worked)
- `@tanstack/react-table` **v8.21.3, deliberately not v9** — see Gotchas
- `recharts` + shadcn's `chart.tsx` wrapper (`ChartContainer`,
  `ChartTooltip`, etc.) — replaces `primevue/chart` (Chart.js). This is
  shadcn's own recommended charting pairing (they ship an official
  Recharts-based chart recipe), not an arbitrary choice.
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
| `src/components/MultiSelect.tsx` | Hand-rolled multi-select (trigger + popover + checkbox list) — shadcn/ui doesn't ship one. Used by `ConfigurationView` (`ml_models`), `InferenceIoTView` (`device_token`), `PlotView`/`ResultCompareView` (metric pickers), `ResultList`/`ResultCompareView` (results-to-compare pickers). Not a `<select multiple>` — needs chip-style selected-item display to match the old UX. |
| `src/components/MetricsTable.tsx` | One result's train/val/test metric rows (rendering half of `logic/format.ts`'s `buildMetricsTable`) — extracted from `ResultList`'s metrics dialog so `ResultCompareView`'s per-result summary cards reuse the exact same markup. |
| `src/components/CodeEditor.tsx` | Hand-rolled Monaco wrapper (refs + `useEffect`, not `@monaco-editor/react` — deliberately not using that library, see Gotchas). Same lazy-loading contract as the Vue version: `monacoEnvironment.ts` + Monaco's core editor module are both loaded via a runtime `import()` inside a mount effect, never from `main.tsx`, so Monaco never lands in the app's main chunk. |
| `src/monacoEnvironment.ts` | Copied unchanged from the Vue app (framework-free side-effect module: worker wiring + python/lua language registration only, not the full 40+-language bundle). |
| `src/components/Layout.tsx` | Sidebar + topbar shell (`<Outlet/>`-based), replaces `App.vue`. Desktop sidebar always visible; mobile uses a shadcn `Sheet` slide-over instead of PrimeVue's `Sidebar`. |
| `src/routes.tsx` | Route table — same paths as the old Vue router, each view `React.lazy`-imported for the same per-route code-splitting the Vue app had. |
| `src/views/*.tsx` | One file per screen, matching the old Vue app's `src/views/*.vue` 1:1 by filename (minus the extension). |

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
   exact version the old Vue app used successfully with this identical
   lazy-loading pattern, so pinning to it (via `npm install
   monaco-editor@0.50.0 --save-exact`) was the pragmatic fix over
   reverse-engineering 0.56.0's new structure. Bonus: this also happens
   to drop a `pnpm audit` `dompurify` advisory that comes in transitively
   via 0.56.0's dependency chain - not why it was pinned, but worth
   knowing if someone re-checks `pnpm audit` later and wonders why it's
   clean here specifically.
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
4. **TypeScript's very-new `"exports"`-strict module resolution can't
   find `monaco-editor`'s deep-import subpaths at all**, even the ones
   that physically exist with real `.d.ts` content
   (`esm/vs/editor/editor.api.d.ts`, the two `basic-languages/{python,lua}/
   *.contribution.d.ts` files) - `monaco-editor`'s own `package.json`
   `exports` map only declares a `types` condition for its root `.`
   entry, not for the `./*` wildcard deep-import pattern this project
   relies on. Vite/esbuild resolve the runtime `.js` for the same
   specifiers fine (bundlers respect the wildcard's plain JS mapping);
   this is purely a `tsc` type-resolution gap. Fixed with explicit
   `paths` entries in `tsconfig.app.json` pointing straight at the
   physical `.d.ts` files, bypassing `exports` resolution entirely for
   just those three specifiers. If `monaco-editor` ever ships a `types`
   condition on that wildcard, these path overrides become redundant
   (harmless to leave, but worth removing then).
5. **`@monaco-editor/react` was deliberately *not* used**, even though
   it's the obvious/default React+Monaco pairing. It wants to own the
   Monaco import/loader lifecycle itself (CDN by default, or its own
   `loader.config({monaco})` bundling path), which conflicts with this
   project's bundle-size-conscious core-only-import strategy
   (`monaco-editor/esm/vs/editor/editor.api`, not the bare
   `monaco-editor` package, which pulls in every language + full
   TS/CSS/HTML/JSON language services - several MB never used here).
   `CodeEditor.tsx` hand-rolls the same ref-based
   create/dispose/watch-props lifecycle the old `CodeEditor.vue` used,
   just expressed as `useEffect`s instead of Vue's `onMounted`/`watch`.
   This is more code than `<Editor/>` would have been, but keeps the
   exact bundle-size guarantee the old Vue app's own "Code editor"
   documentation described and tested for (confirmed: this app's
   `editor.api` chunk is 579 kB gzipped after `pnpm build` - same order
   of magnitude as the Vue app's own documented ~594 kB figure, not the
   multi-MB full bundle `@monaco-editor/react`'s default CDN path would
   pull down).
6. **The Dockerfile must copy all three tsconfig files, not just
   `tsconfig.json`.** This project uses TS project references
   (`tsconfig.json` has `"files": []` + `"references"` to
   `tsconfig.app.json`/`tsconfig.node.json`, no `compilerOptions` of its
   own for the actual source). `pnpm build` runs `tsc -b`, which follows
   those references - copying only `tsconfig.json` into the build stage
   would fail the Docker build the moment `tsc -b` tries to resolve a
   reference to a file that was never copied in. Caught by actually
   building the image, not by inspection - `pnpm build` run locally
   against the full source tree never exercises this, since every file
   is already present there regardless of what a Dockerfile's `COPY`
   list says.

## Backend contract gotchas (learned the hard way — keep these)

Backend wire-contract facts, not frontend-framework-specific — apply to
any frontend that talks to this backend:

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

## Runtime configuration / Docker

`Dockerfile`, `nginx-custom.conf`, `start.sh`, `public/env.template.js` all
use the same contract the deployed frontend has always used — same
`BACKEND_URL`/`BACKEND_PROXY_URL`/`ENABLE_FEDML_BLOCKCHAIN` env vars, same
`/api` nginx proxy + WebSocket upgrade handling, same `window.env`
runtime-config pattern. This is why the cutover needed zero changes to the
k8s deployment YAML beyond what already pointed at image name
`kafka-ml-frontend`.

## Testing approach

```bash
pnpm test:run     # Vitest + React Testing Library, 98 tests
pnpm typecheck    # tsc -b --noEmit
pnpm build        # tsc -b && vite build (also typechecks)
pnpm test:e2e     # Playwright, real browser, mocked /api/* - see below
```

98 unit/component tests total: most are the ported `src/logic/*.test.ts` +
`src/api.test.ts` + `src/ws.test.ts` files (unchanged from the Vue app,
proving the ported business logic still behaves identically), plus
`routes.test.ts` (every view module resolves without throwing - same
cheap regression net the Vue app's `router.test.ts` had) and
component-level tests (`ModelList.test.tsx`, `ConfigurationView.test.tsx`,
and later additions like the `InferenceList` modal coverage).

**Real, committed E2E suite (2026-08-06)**: `e2e/golden-path.spec.ts`,
run via `pnpm run test:e2e` / CI's `frontend.yml` (not vitest - excluded
from it explicitly in `vite.config.ts`'s `test.exclude`, different
runner/API). Drives the real app (real routing, real forms, the real
Monaco editor - no mocking of the app's own code) through create model →
create configuration → deploy → simulate a training Job finishing (no
CI runner can do that against a real cluster) → view real metrics →
deploy the result for inference, plus two smaller specs. Every `/api/*`
call is intercepted and answered by `e2e/mock-backend.ts`, a small
stateful fake sharing the test process's JS heap (so a test can mutate
`backend.results` etc. directly between steps, no bridging needed) -
same spirit as `kafkaml-client/tests`' fake backend, for the same reason
a cluster-backed E2E run isn't something CI can realistically do.
Monaco has no test hooks (it's the hand-rolled wrapper described above,
not a library with a testing API) - the spec drives it the standard way,
clicking into `.monaco-editor` and using `page.keyboard.type()`.

**Found two real bugs writing this, not just test-authoring friction**:
see `CodeEditor.tsx`'s own `[value]`-sync effect comment for a genuine
infinite-render-loop crash (real users typing multi-line indented code
quickly enough could hit it - not Playwright-specific) and its
value-comparison fix; and see `FUTURE.md`'s "No end-to-end tests" entry
for a `DeploymentList.tsx` crash the mock backend's first draft exposed
(not a real backend gap, confirmed against `backend/app/schemas/
__init__.py` - the mock's own bug, but `DeploymentList.tsx` itself had no
defensive fallback either).

Earlier ad hoc Playwright verification (a throwaway, uncommitted script
driving `pnpm dev` against the live local backend through every main
view + a dark-mode toggle, plus the production nginx Docker image
deployed to the local cluster) is superseded by the committed suite
above for anything it covers, but its finding still stands as the more
recent proof of real-backend integration: zero console errors, correct
Monaco rendering, correct dark-mode repaints.

## Training-results comparison view (2026-08-06)

`/results/compare?ids=1,2,...` (`ResultCompareView.tsx`) overlays 2-5
training results' metric curves side by side - one facet (chart) per
metric, one line per (result, split), so "did this hyperparameter change
help?" doesn't mean manually eyeballing two separate metric dialogs.
Reached from `ResultList.tsx`'s new "Compare results" `MultiSelect` picker
above the table. Query string, not a path param (`?ids=`, not `/:ids`) -
a set of ids to compare is a filter/selection, not a resource identifier,
and it lets the compare page itself add/remove results via
`setSearchParams` with zero extra fetch (the full `getResults()` list is
already fetched to resolve the picked ids). Verified this is genuinely new
territory for the router (a static `/results/compare` next to the existing
dynamic `/results/:id`) by reading react-router 7's own ranking source -
static segments always outrank dynamic ones, so this is safe regardless of
array order - then confirmed live in a browser anyway, not just trusted
the math.

Design, all in `src/logic/plot.ts` (`MAX_COMPARE_RESULTS`, `parseCompareIds`,
`availableComparisonMetricNames`, `buildComparisonChartData`,
`toRechartsData` promoted out of `PlotView`'s former private copy):
small multiples (one chart per metric) rather than one mega chart with
every metric/result/split overlaid - facets N results x M metrics x 2
splits into per-metric charts of just N x 2 lines each, same convention
TensorBoard/W&B already use for this. Composite encoding within a facet:
color = result identity (the app's existing 5-slot `--chart-1`..`--chart-5`
theme-aware palette, `index.css` - not a new palette, hence the 5-result
cap), line style = split (solid = train, dashed = validation). A shorter
run's line visibly stops rather than flattening out (no data past its own
length, not padded with fabricated values) - confirmed live with two real
seeded results (3 vs. 6 epochs). `MetricsTable.tsx` was extracted from
`ResultList`'s metrics dialog (zero behavior change there) so the compare
view's per-result summary cards reuse it instead of a new pivot function.

Verified against 2 real finished CASE=1 results seeded through the actual
API/Kafka (same approach as `integration-tests/test_case1_single_classic.py`),
not just the mocked E2E suite - confirmed the URL routing doesn't fall
through to `ResultList`, correct color-per-result and dash-per-split
rendering, tooltip disambiguates train vs. validation per result (initially
didn't - both lines of one result showed an identical label, only the
value differed - fixed by suffixing the `ChartConfig` label with
"(training)"/"(validation)"), dark-mode toggle actually changes the
rendered line colors (since they're `var(--chart-N)` references, not
resolved hex strings - a bar `PlotView` itself doesn't clear), and a
malformed `?ids=999,abc` shows a friendly "not found" message instead of
crashing.

## Berry language support for IoT device scripts (2026-08-06)

`InferenceIoTView.tsx`'s "Berry Script for Tasmota" field used to render
with `language="lua"` — the closest built-in Monaco grammar, but wrong:
Tasmota's scripting engine is [Berry](https://github.com/berry-lang/berry),
not Lua, and the two differ in real ways a "close enough" grammar gets
wrong (comments are `#`/`#- -#`, not `--`/`--[[ ]]`; blocks close with a
single `end` keyword, not Lua's `then`/`do`/`function`-specific
terminators; no `local`, no `function` keyword, `var`/`def` instead).
Monaco has no built-in Berry grammar, so `src/berryLanguage.ts` hand-writes
one, sourced directly from Berry's own authoritative references (fetched
from `berry-lang/berry`'s `tools/` directory, not guessed): the official
Pygments lexer (`tools/highlighters/Pygments/berry.py`) for the
keyword/builtin/string/comment token classes, and the EBNF grammar
(`tools/grammar/berry.ebnf`) for the full operator set (walrus `:=`, range
`..`, lambda arrow `->`, compound assignment). Registered directly against
Monaco's public `monaco.languages.register`/`setLanguageConfiguration`/
`setMonarchTokensProvider` API in `monacoEnvironment.ts`, since — unlike
Python/Lua — there's no bundled `basic-languages/berry/*.contribution`
module to lazily import (Monaco ships no Berry grammar at all).

Gotcha: an untyped Monarch tokenizer object literal gets its rule arrays
widened by TypeScript to `(string | RegExp)[]` instead of the fixed-length
tuples `IMonarchLanguageRule` actually requires, failing `pnpm typecheck`
with `Type '(string | RegExp)[]' is not assignable to type
'IShortMonarchLanguageRule2'`. Fixed by adding an explicit
`: Monaco.languages.IMonarchLanguage` type annotation on the
`berryLanguageDefinition` export so each rule gets checked in the right
contextual type from the start.

Verified live: typed a real Berry sample (keywords, an `f"..."` f-string, a
`#- -#` block comment, a `#` line comment, the `..` range operator) into
the field via Playwright against the real dev server, confirmed Monaco
actually assigned distinct token classes per construct (not all falling
back to one plain-text class) and that the editor's own language indicator
reads "berry", not "lua" — screenshot-verified keyword/comment/string/number
coloring is genuinely differentiated, zero console errors.

## Importing a trained model (2026-08-07)

`ImportDeploymentView.tsx` (`/import/:id`, reached from
`ConfigurationList`'s "Import trained model" dropdown item) has no Vue-app
equivalent - this is a genuinely new screen, not a port, since the
feature itself is new (see `backend/CLAUDE.md`'s matching section). Loads
the configuration + `getDistributedConfiguration`, same pattern
`DeploymentView.tsx` already uses, and shows an explanatory message
instead of the form when the configuration isn't exactly one
non-distributed model (distributed gets its own specific message, not
the generic one, matching the backend's own error-ordering choice).

`api.ts`'s `importDeployment` is the first `multipart/form-data` write
this frontend makes - every other write goes through `request()`'s
shared JSON-encoding helper, so this one bypasses it and builds a
`FormData`/`fetch` call directly rather than trying to force a file
upload through a JSON-only helper.

Metrics (train/val/test, all optional) are entered as raw JSON strings
in plain `Input`s, same convention `DeploymentView.tsx`'s federated
`data_restriction` field already uses for free-form JSON - not a
structured form, since metric shapes are arbitrary dicts.

Verified live end-to-end against the real deployed cluster (not just
`ImportDeploymentView.test.tsx`'s 7 mocked-API tests): real model +
configuration created via the actual API, a real `.h5` file uploaded
through the real rendered form and Import button, confirmed the success
toast, the navigation to `/deployments/:id`, and the new finished result
actually appearing there - zero console errors throughout.

## Remaining work

1. **Feature-parity audit vs. the old Vue app hasn't been done by a human
   yet** - same caveat the Vue app itself had against the Angular app it
   replaced. This rewrite was verified against the live backend
   end-to-end (see above) but not clicked through screen-by-screen by a
   person yet.
2. ~~No end-to-end/integration test suite.~~ — **done** (2026-08-06, see
   "Testing approach" above).
3. ~~`reactflow` is installed but unused.~~ — **removed** (2026-08-06,
   `FUTURE.md` frontend-follow-ups #5): confirmed zero imports anywhere
   in `src/`, dropped from `package.json`. Revisit (re-add) if a real
   pipeline-topology view ever gets requested - nothing else depends on
   it having been here.
4. ~~`@tanstack/react-query` is installed but unused.~~ — **removed**
   (2026-08-06): turned out to be more than dead weight - `main.tsx` was
   actually mounting a live `QueryClientProvider`/`QueryClient` around
   the whole app, even though zero components anywhere call
   `useQuery`/`useMutation` - real unused runtime cost, not just an
   unused import. Removed the provider wrapper along with the
   dependency; every view still hand-rolls its own fetch effect, exactly
   as before. `pnpm test:run` (83 tests), `pnpm typecheck`, and `pnpm
   build` all still pass clean.
5. ~~No accessibility pass on the sidebar/theme-toggle shell or Monaco
   fields.~~ — **done** (2026-08-06, `FUTURE.md` frontend-follow-ups #6):
   skip-to-main-content link (found and fixed a real bug while verifying
   it live - `<main>` needs `tabIndex={-1}` or the link only scrolls, it
   never moves keyboard focus), labeled nav landmark, `aria-expanded`/
   `aria-controls` on the mobile menu trigger, `aria-pressed` on both
   theme-toggle buttons, and an `ariaLabel` prop on `CodeEditor` wired into
   Monaco's own accessibility option (previously every instance on a page
   announced identically to a screen reader - `ModelView` has two).
   Surfaced a wider, explicitly out-of-scope-for-this-pass finding: ~19
   icon-only buttons across the list views rely on a bare `title` for
   their accessible name (verified this still resolves correctly via the
   HTML spec's title-fallback, just not keyboard-focus-visible the way
   hover tooltips are) - see `FUTURE.md`'s entry for the file list.
