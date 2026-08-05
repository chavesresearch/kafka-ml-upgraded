## What does this change do, and why?

<!-- Describe the change. For anything touching training-mode behavior,
say which CASE(s) this affects and how you verified it. -->

## Affected component(s)

<!-- e.g. backend, model_training/tensorflow, federated-module, frontend -->

## How was this tested?

- [ ] Ran the affected subproject's own test suite (`uv run pytest -v` / `pnpm run test:run`)
- [ ] Verified against a real deployment (not just unit tests) - describe how, if applicable
- [ ] N/A (docs-only / CI-only change)

## Checklist

- [ ] I've read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] This PR is scoped to one subproject/concern (not a mix of unrelated changes)
- [ ] I haven't broken the existing API/wire-format contracts other services depend on (or I've called out the breaking change explicitly)
