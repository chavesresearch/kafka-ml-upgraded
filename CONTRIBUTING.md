# Contributing to Kafka-ML

Thanks for considering a contribution! Kafka-ML is a research-originated
project (see the [publication](README.md#kafka-ml-connecting-the-data-stream-with-mlai-frameworks)
in the README) that also takes contributions from the wider community.

## Before you start

For anything non-trivial - a new feature, a change to the training-mode
dispatch (the `CASE` 1-9 logic), a dependency bump that isn't a routine
patch release - please open an issue first to discuss the approach. It
saves everyone rework, and some parts of this codebase have
non-obvious constraints (e.g. Kubernetes RBAC scoping, the Kafka wire
formats different services agree on) that are easy to get subtly wrong
without context.

For small fixes (typos, a clear bug with an obvious fix, a flaky test),
feel free to open a PR directly.

## Repository layout

This is a monorepo of many independently deployable services, each with
its own dependency manifest and test suite:

- `backend/`, `federated-module/federated_backend/` - Litestar/Python APIs
- `frontend/` - React 19 + shadcn/ui
- `model_training/`, `model_inference/`, `federated-module/federated_model_training/` - TensorFlow/PyTorch training and inference containers
- `mlcode_executor/` - the tf/pth code-validation services
- `datasources/`, `kafkaml-client/`, `tf-kafka-dataset/` - Python client libraries
- `kustomize/`, `federated-module/kustomize/` - Kubernetes deployment manifests

Each Python subproject uses [uv](https://docs.astral.sh/uv/); each has its
own `pyproject.toml`/`uv.lock` and its own `tests/` directory. `frontend/`
uses `pnpm`.

## Making a change

1. Fork the repo and create a branch off `master`.
2. Make your change in the relevant subproject(s) only - avoid touching
   unrelated services in the same PR.
3. Run that subproject's own test suite before opening a PR:
   ```sh
   cd <subproject>
   uv run pytest -v        # Python services
   pnpm run test:run        # frontend/, website/
   ```
4. Every push and PR runs the matching `.github/workflows/<subproject>.yml`
   CI job automatically - check that it's green.
5. Open a PR against `master`. Describe *what* changed and *why* - for
   anything touching training-mode behavior, describing how you verified
   it (which `CASE`, what data) is especially useful, since the platform's
   correctness ultimately depends on real end-to-end behavior, not just
   unit tests.

## Reporting bugs

Open a [GitHub issue](../../issues) with:
- what you expected vs. what happened
- the affected service/subproject
- steps to reproduce, including relevant `CASE` number if it's
  training-mode-specific

For security vulnerabilities, see [SECURITY.md](SECURITY.md) instead of
opening a public issue.

## License

By contributing, you agree that your contributions will be licensed
under the project's [MIT License](LICENSE).
