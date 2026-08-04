# --build-arg TFTAG=2.21.0-gpu for GPU version
#
# Build context must be the repo root (kafka-ml-upgraded/), not this
# directory, since this trainer now depends on the sibling
# ../../tf-kafka-dataset package via a relative [tool.uv.sources] path:
#   docker build -f model_training/tensorflow/Dockerfile \
#     -t kafka-ml-model-training-tensorflow:test .
ARG TFTAG=2.21.0
FROM tensorflow/tensorflow:${TFTAG}

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

# tf-kafka-dataset, at the same relative depth
# (/usr/src/app/../../tf-kafka-dataset) this trainer's pyproject.toml
# references locally
COPY tf-kafka-dataset /usr/tf-kafka-dataset

# install dependencies (separate layer from the source copy below, so
# dependency installs are cached across code-only changes)
COPY model_training/tensorflow/pyproject.toml model_training/tensorflow/uv.lock ./
RUN uv sync --locked --no-install-project

# copy project
COPY model_training/tensorflow/. /usr/src/app/
RUN uv sync --locked

RUN chmod +x ./start.sh

# Run as non-root - this trainer exec()s user-submitted model code (see
# FUTURE.md's exec() hardening note), so it should never run as root even
# though nothing here needs root today.
RUN useradd --create-home --uid 1000 kafkaml && chown -R kafkaml:kafkaml /usr/src/app
USER kafkaml

CMD ["./start.sh"]
