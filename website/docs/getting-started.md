---
sidebar_position: 3
---

# Getting Started

## Requirements

- [Docker](https://www.docker.com/)
- [Kubernetes >= v1.15.5](https://kubernetes.io/)

## Deploy Kafka-ML in a fast way

For a basic local installation, we recommend using Docker Desktop with
Kubernetes enabled. Follow the installation guide on [Docker's
website](https://docs.docker.com/desktop/); to enable Kubernetes, see
[Enable Kubernetes](https://docs.docker.com/desktop/kubernetes/#enable-kubernetes).

Once Kubernetes is running, open a terminal and run:

```sh
# Uncomment only if you are running Kafka-ML on Apple Silicon
# export DOCKER_DEFAULT_PLATFORM=linux/amd64
kubectl apply -k "github.com/chavesresearch/kafka-ml-upgraded/kustomize/local"
```

This installs every Kafka-ML component, plus Kafka itself, into the
`kafkaml` namespace. The Web UI will be available at
[http://localhost/](http://localhost/).

Continue with [Single Models](./usage/single-models) to try the golden
path, or browse the [Interactive Showcase](/showcase) first if you'd
rather see how the different training modes work before standing up a
cluster.

For building images and deploying step-by-step instead, see
[Installation and Development](./installation/build).
