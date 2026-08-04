---
sidebar_position: 3
---

# Distributed Cluster Deployment

## Configuring the backend

Images built for a single-node cluster (`localhost`) won't be pullable
from a distributed cluster. Push each image to a registry reachable by
every node instead — for example, on a node with IP `x.x.x.x`:

```bash
cd backend
docker build --tag x.x.x.x:5000/backend .
docker push x.x.x.x:5000/backend
```

Repeat for every image, then update `backend-deployment.yaml`:

```yaml
 containers:
 -   - image: localhost:5000/backend
 +   - image: x.x.x.x:5000/backend

    - name: BOOTSTRAP_SERVERS
      value: kafka-cluster:9092 # all your Kafka bootstrap servers, comma-separated

    - name: TRAINING_MODEL_IMAGE
-     value: localhost:5000/model_training
+     value: x.x.x.x:5000/model_training
    - name: INFERENCE_MODEL_IMAGE
-     value: localhost:5000/model_inference
+     value: x.x.x.x:5000/model_inference
    - name: FRONTEND_URL
-     value: http://localhost
+     value: http://x.x.x.x
```

And `frontend-deployment.yaml`:

```yaml
 containers:
 -   - image: localhost:5000/backend
 +   - image: x.x.x.x:5000/backend

    - name: BACKEND_URL
-     value: http://localhost:8000
+     value: http://x.x.x.x:8000
```

To let `backend` create Jobs/Deployments on the cluster, create a
service account, bind it to `cluster-admin`, and get its token:

```bash
sudo kubectl create serviceaccount k8sadmin -n kube-system
sudo kubectl create clusterrolebinding k8sadmin --clusterrole=cluster-admin --serviceaccount=kube-system:k8sadmin
sudo kubectl -n kube-system describe secret $(sudo kubectl -n kube-system get secret | (grep k8sadmin || echo "$_") | awk '{print $1}') | grep token: | awk '{print $2}'
```

Set the resulting token as `KUBE_TOKEN`, and `KUBE_HOST` to the
Kubernetes master's URL (e.g. `https://IP_MASTER:6443`), in
`backend-deployment.yaml`:

```
    - name: KUBE_TOKEN
      value: # include token here
    - name: KUBE_HOST
      value: # include kubernetes master URL here
```

Finally, to reach the backend from outside the cluster, assign an
external node IP to its service in `backend-service.yaml`:

```
  type: LoadBalancer
+ externalIPs:
+ - y.y.y.y
```

...and add that IP to `ALLOWED_HOSTS`:

```
    - name: ALLOWED_HOSTS
      value: y.y.y.y, localhost
```
