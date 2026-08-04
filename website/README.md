# Kafka-ML website

The Kafka-ML docs, SDK reference, and interactive showcase site, built
with [Docusaurus](https://docusaurus.io/) and deployed to GitHub Pages
via `.github/workflows/website.yml`.

## Layout

- `docs/` — the main tool documentation, sourced from and kept in sync
  with the root `README.md`'s content (Usage tutorials, installation,
  security threat model, etc.).
- `sdk/` — a second, independent docs instance (its own sidebar, own
  `/sdk/` route) for the `kafkaml-client` Python SDK.
- `src/pages/showcase/` + `src/components/Showcase/` — the interactive
  showcase: all 9 real training modes (`model_training/tensorflow`'s
  `CASE` 1-9), each with an animated architecture diagram, real example
  code, and simulated (not real) metrics.
- `src/pages/index.tsx` — the landing page.

## Local development

```bash
pnpm install
pnpm start
```

Starts a dev server with hot reload at `/kafka-ml-upgraded/` (the
production `baseUrl` is set in `docusaurus.config.ts` so local dev
matches the deployed path exactly).

## Build

```bash
pnpm run typecheck
pnpm run build
pnpm run serve   # serve the production build locally to sanity-check it
```

## Deployment

Deployment is automatic via `.github/workflows/website.yml` on every
push to `master` that touches `website/**` - it builds the site and
publishes it through GitHub's native Pages-from-Actions flow
(`actions/upload-pages-artifact` + `actions/deploy-pages`), not the
`docusaurus deploy`/`gh-pages` branch method.

**One-time manual step** (can't be done from the CLI): in the repo's
GitHub Settings → Pages, set "Build and deployment: Source" to **GitHub
Actions**.
