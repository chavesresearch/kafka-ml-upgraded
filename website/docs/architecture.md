---
sidebar_position: 2
---

# Architecture

Kafka-ML's pipeline connects five kinds of moving pieces: a web UI and
API for defining models, Apache Kafka as the data transport, a set of
"code executor" services that validate model code before it runs,
Kubernetes Jobs/Deployments that actually train and serve models, and
(for federated learning) a small satellite service that coordinates edge
devices.

![Kafka-ML pipeline architecture](/img/docs/pipeline_.png)

## Components

| Component | Role |
|---|---|
| **`backend`** | The REST API — models, configurations, deployments, results, inference, IoT devices. Creates the real Kubernetes Jobs/Deployments/ReplicationControllers that do the actual training and inference. |
| **`frontend`** | The Web UI. Everything in this doc's tutorials (defining a model, deploying a configuration, watching metrics) happens here. |
| **`mlcode_executor`** (`tfexecutor` / `pthexecutor`) | Validates model code by actually `exec()`-ing it, before a model is allowed to be saved or deployed. One service per framework. |
| **`model_training`** (`tensorflow` / `pytorch`) | The training containers. Consume a Kafka data stream, train the model, report metrics back to `backend`. This is where the 9 training modes (single/distributed/federated × classic/incremental, plus blockchain) are actually dispatched — see the [Interactive Showcase](/showcase). |
| **`model_inference`** (`tensorflow` / `pytorch`) | Serves a trained model: consumes an input Kafka topic, produces predictions to an output topic. |
| **`federated-module`** | A satellite service (`federated_backend` + two Kafka-to-HTTP relay loggers + its own `federated_model_training` edge worker image) that coordinates federated learning rounds — matching registered datasources against registered models and launching edge-device training Jobs. |
| **`datasources`** (`kafkaml-datasources` package) | Client-side helpers for sending training/inference data into Kafka in the shape Kafka-ML expects (RAW, Avro, federated and online/streaming variants). |
| **`kafka_control_logger`** | Relays Kafka control-topic messages (new datasource registrations) into `backend` over HTTP. |
| **[`kafkaml-client`](/sdk/intro)** | A Python SDK wrapping the REST API, as an alternative to using the Web UI or raw HTTP calls directly — see the [SDK docs](/sdk/intro). |

## The training pipeline, end to end

1. **Define a model** in the Web UI (or via the [SDK](/sdk/creating-models)) — real Python/Keras or PyTorch code, checked by the matching `mlcode_executor` before it's accepted.
2. **Group it into a configuration** — one or more models trained together (useful for comparing models, or for the father/child chain a distributed model needs).
3. **Deploy the configuration** — `backend` submits a real Kubernetes Job running `model_training`.
4. **Stream data** — a client sends training data into Kafka using `kafkaml-datasources`; the training Job consumes it, trains, and reports metrics back.
5. **Deploy for inference** — once trained, deploy the result as a `model_inference` Job/ReplicationController that consumes a live input topic and produces predictions.

Distributed, incremental, federated, and blockchain-traced modes all
follow this same shape with extra coordination — see [Distributed
Models](./usage/distributed-models), [Incremental
Training](./usage/incremental-training), and [Federated
Learning](./usage/federated-learning) for what changes in each, or jump
straight to the [Interactive Showcase](/showcase) to see all 9 side by
side.
