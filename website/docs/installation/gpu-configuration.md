---
sidebar_position: 4
---

# GPU Configuration

Steps to enable GPU acceleration in Kafka-ML and Kubernetes — run these
on every GPU-equipped Kubernetes node.

## 1. GPU driver installation

```bash
# SSH into the worker machine with GPU
ssh USERNAME@EXTERNAL_IP

# Verify Ubuntu driver
sudo apt install ubuntu-drivers-common
ubuntu-drivers devices

# Install the recommended driver
sudo ubuntu-drivers autoinstall

# Reboot, then confirm
sudo reboot
nvidia-smi
```

## 2. NVIDIA Docker installation

```bash
ssh USERNAME@EXTERNAL_IP

distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

## 3. Docker daemon configuration

```bash
ssh USERNAME@EXTERNAL_IP
sudo tee /etc/docker/daemon.json <<EOF
{
    "default-runtime": "nvidia",
    "runtimes": {
        "nvidia": {
            "path": "/usr/bin/nvidia-container-runtime",
            "runtimeArgs": []
        }
    }
}
EOF
sudo pkill -SIGHUP docker
sudo reboot
```

## 4. Kubernetes GPU-sharing extension

```bash
# From your local machine, with access to the Kubernetes API
curl -O https://raw.githubusercontent.com/AliyunContainerService/gpushare-scheduler-extender/master/config/gpushare-schd-extender.yaml
kubectl create -f gpushare-schd-extender.yaml

wget https://raw.githubusercontent.com/AliyunContainerService/gpushare-device-plugin/master/device-plugin-rbac.yaml
kubectl create -f device-plugin-rbac.yaml

wget https://raw.githubusercontent.com/AliyunContainerService/gpushare-device-plugin/master/device-plugin-ds.yaml
# update the local file so the first line is 'apiVersion: apps/v1'
kubectl create -f device-plugin-ds.yaml

kubectl label node worker-gpu-0 gpushare=true
```

Thanks to Sven Degroote from ML6team for the original GPU + Kubernetes
setup [documentation](https://blog.ml6.eu/a-guide-to-gpu-sharing-on-top-of-kubernetes-6097935ababf).
