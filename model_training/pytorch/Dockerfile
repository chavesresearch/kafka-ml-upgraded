# --build-arg BASEIMG=pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime for GPU
# version (also drop the [tool.uv] pytorch-cpu index section in
# pyproject.toml - see the comment there)
ARG BASEIMG=python:3.12-slim
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

RUN chmod +x ./start.sh

# Run as non-root - this trainer exec()s user-submitted model code (see
# FUTURE.md's exec() hardening note), so it should never run as root even
# though nothing here needs root today.
RUN useradd --create-home --uid 1000 kafkaml && chown -R kafkaml:kafkaml /usr/src/app
USER kafkaml

CMD ["./start.sh"]
