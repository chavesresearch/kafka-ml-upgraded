# --build-arg TFTAG=2.21.0-gpu for GPU version
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

# install dependencies (separate layer from the source copy below, so
# dependency installs are cached across code-only changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

# copy project
COPY . /usr/src/app/
RUN uv sync --locked

RUN chmod +x ./start.sh

# Run as non-root - defense in depth for consistency with the other
# services (this one doesn't exec() user code itself - it loads a
# serialized .h5 file - but model_inference/pytorch does, see its own
# Dockerfile, and there's no reason for this one to run privileged
# either).
RUN useradd --create-home --uid 1000 kafkaml && chown -R kafkaml:kafkaml /usr/src/app
USER kafkaml

CMD ["./start.sh"]
