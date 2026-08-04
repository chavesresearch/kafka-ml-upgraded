---
sidebar_position: 2
---

# Single-Node Deployment

Once your images are built (see [Building Kafka-ML](./build)), deploy
the components in a single-node cluster (e.g. minikube, Docker Desktop)
in this order:

```
kubectl apply -f zookeeper-pod.yaml
kubectl apply -f zookeeper-service.yaml

kubectl apply -f kafka-pod.yaml
kubectl apply -f kafka-service.yaml

kubectl apply -f backend-deployment.yaml
kubectl apply -f backend-service.yaml

kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml

kubectl apply -f tf-executor-deployment.yaml
kubectl apply -f tf-executor-service.yaml

kubectl apply -f pth-executor-deployment.yaml
kubectl apply -f pth-executor-service.yaml

kubectl apply -f kafka-control-logger-deployment.yaml
```

The Web UI will then be available at [http://localhost/](http://localhost/).
