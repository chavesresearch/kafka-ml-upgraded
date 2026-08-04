---
sidebar_position: 1
---

# Building Kafka-ML

If you want to build Kafka-ML yourself instead of using pre-built
images — to contribute, or to run a customized version — here's how.

## Requirements

- [uv](https://docs.astral.sh/uv/) — Python dependency management for
  every backend/ML service (`backend`, `mlcode_executor`,
  `model_training`, `model_inference`, `federated-module`,
  `kafka_control_logger`, `datasources`). Each is its own `uv` project
  (`pyproject.toml` + `uv.lock`, no `requirements.txt`) — `uv sync` inside
  any of them installs its dependencies for local development.
- [Node.js](https://nodejs.org/) 22+ and [pnpm](https://pnpm.io/) 11 —
  for `frontend` (React 19 + TypeScript + Vite).
- [Docker](https://www.docker.com/)
- [Kubernetes >= v1.15.5](https://kubernetes.io/)

## Steps to build Kafka-ML

For a fast local build, set `LOCAL_BUILD` to `true` in the build scripts
and point the deployment files at your local images, then run the build
scripts.

By default, images build CPU-only. For GPU acceleration, pass the
`--build-arg` documented at the top of each `Dockerfile` in
`mlcode_executor`, `model_inference`, and `model_training` (e.g.
`TFTAG=2.21.0-gpu`,
`BASEIMG=pytorch/pytorch:2.13.0-cuda12.6-cudnn9-runtime`).

To build step by step instead:

1. Deploy a local registry (port 5000):

   ```bash
   docker run -d -p 5000:5000 --restart=always --name registry registry:2
   ```

2. Build the backend and push it:

   ```bash
   cd backend
   docker build --tag localhost:5000/backend .
   docker push localhost:5000/backend
   ```

3. Build the ML code executors:

   ```bash
   cd mlcode_executor/tfexecutor
   docker build --tag localhost:5000/tfexecutor .
   docker push localhost:5000/tfexecutor

   cd ../pthexecutor
   docker build --tag localhost:5000/pthexecutor .
   docker push localhost:5000/pthexecutor
   ```

4. Build the training components:

   ```bash
   cd model_training/tensorflow
   docker build --tag localhost:5000/tensorflow_model_training .
   docker push localhost:5000/tensorflow_model_training

   cd ../pytorch
   docker build --tag localhost:5000/pytorch_model_training .
   docker push localhost:5000/pytorch_model_training
   ```

5. Build `kafka_control_logger`:

   ```bash
   cd kafka_control_logger
   docker build --tag localhost:5000/kafka_control_logger .
   docker push localhost:5000/kafka_control_logger
   ```

6. Build the inference components:

   ```bash
   cd model_inference/tensorflow
   docker build --tag localhost:5000/tensorflow_model_inference .
   docker push localhost:5000/tensorflow_model_inference

   cd ../pytorch
   docker build --tag localhost:5000/pytorch_model_inference .
   docker push localhost:5000/pytorch_model_inference
   ```

7. Build the frontend:

   ```bash
   cd frontend
   pnpm install --frozen-lockfile
   pnpm run build
   docker build --tag localhost:5000/frontend .
   docker push localhost:5000/frontend
   ```

Next: [deploying to a single-node
cluster](./single-node) or a [distributed
cluster](./distributed-cluster).
