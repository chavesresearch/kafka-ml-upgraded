# pull official base image
FROM python:3.12-slim

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
CMD ["./start.sh"]
