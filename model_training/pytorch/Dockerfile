# --build-arg BASEIMG=pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime for GPU
# version (also drop the [tool.uv] pytorch-cpu index section in
# pyproject.toml - see the comment there)
ARG BASEIMG=python:3.14-slim
FROM ${BASEIMG}

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/usr/src/app/.venv
ENV UV_COMPILE_BYTECODE=1

# install uv
RUN pip install --upgrade pip
RUN pip install uv

# install dependencies (separate layer from the source copy below, so
# dependency installs are cached across code-only changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

# copy project
COPY . /usr/src/app/
RUN uv sync --locked

# `uv sync --locked` above always installs the *lockfile's* torch/
# torchvision - CPU-only, since uv.lock is resolved against the
# pytorch-cpu index pinned in pyproject.toml's [tool.uv.sources]
# regardless of BASEIMG. The GPU base image (pytorch/pytorch:*-cuda*) has
# a CUDA-enabled torch preinstalled in its *system* Python, but that's
# irrelevant here - uv creates its own isolated .venv
# (UV_PROJECT_ENVIRONMENT above) that never touches it. Previously this
# meant every "-gpu" image built and pushed successfully while silently
# still running CPU-only torch. When actually building for GPU, reinstall
# both from the plain PyPI index instead (confirmed via PyPI's own JSON
# API - its Linux torch==2.13.0 wheel is 526MB, consistent with a
# CUDA-bundled build, not the ~200MB a CPU-only wheel would be) so the
# image's own torch matches what its tag promises.
ARG TORCH_VARIANT=cpu
RUN if [ "$TORCH_VARIANT" = "gpu" ]; then \
      uv pip install --python /usr/src/app/.venv/bin/python \
        --reinstall --index-url https://pypi.org/simple \
        torch==2.13.0 torchvision==0.28.0; \
    fi

RUN chmod +x ./start.sh

# Run as non-root - this trainer exec()s user-submitted model code (see
# FUTURE.md's exec() hardening note), so it should never run as root even
# though nothing here needs root today.
RUN useradd --create-home --uid 1000 kafkaml && chown -R kafkaml:kafkaml /usr/src/app
USER kafkaml

CMD ["./start.sh"]
