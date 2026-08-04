# PyTorch Executor (Litestar)

This is a port of `../../mlcode_executor/pthexecutor` from [Flask](https://flask.palletsprojects.com/) to [Litestar](https://litestar.dev/), the same stack `../../backend` uses, plus a dependency refresh: PyTorch 1.10.0 → **2.13.0** (torchvision 0.28.0, pytorch-ignite 0.5.5 - the matching current releases; see `requirements.txt`).

Unlike the TensorFlow executor, this one had no tensorflow-io-style blocker - PyTorch/torchvision/ignite have no Kafka or serialization dependency baked in, so this is a much more direct port. The HTTP contract (`POST /exec_pth/`, `/check_deploy_config/`) is unchanged.

## Installation for local development

Dependencies are managed with [uv](https://docs.astral.sh/uv/) - `pyproject.toml` + `uv.lock`, no `requirements.txt`.

```
uv sync
```

`pyproject.toml` installs the CPU build of torch/torchvision by default (via a `[tool.uv.sources]`-pinned, `explicit = true` extra index at `download.pytorch.org/whl/cpu`, matching the default `python:3.12-slim` base image in `Dockerfile`). For GPU, see the comments in both files.

## Running server

```
uv run uvicorn app:app --host 0.0.0.0 --port 8002
```

If you change the IP or port, also update `PTHEXECUTOR_URL` in whichever backend is deployed.

## Behavioral notes vs. the Flask version

- Route handlers are plain `def` (not `async def`) with `sync_to_thread=True` so Litestar runs the blocking torch/ignite calls in a worker thread instead of on the event loop - see the accompanying `CLAUDE.md`.
- `from ignite.metrics import *` and the `torchvision.models`/`keras`/`tfds`-style module-level imports are kept even where this file doesn't reference them directly: `exec_model()` runs user-submitted model code via `exec(model_code, None, globals())`, so those names need to already be bound in this module's globals for that code to use them unqualified (e.g. a submitted model referencing `Accuracy()`). Don't "clean up" these as unused imports.
