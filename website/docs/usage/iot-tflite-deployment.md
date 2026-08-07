---
sidebar_position: 7
---

# IoT / TFLite Deployment

Deploys a trained model to run **on the device itself** — a
[Tasmota](https://tasmota.github.io/docs/)-flashed microcontroller with
the Berry scripting engine — as a converted `.tflite` model, instead of
as a real-time inference pod in the cluster. Once deployed, inference
happens entirely on-device; no Kafka round-trip per prediction. This is
a different deployment target from [Single Models](./single-models)
step 6's real-time inference — that one runs in Kubernetes and talks to
the device over Kafka, this one runs *on* the device.

Currently only TensorFlow supports IoT deployment — a training result's
model is stored as `.h5`, and only `mlcode_executor/tfexecutor` can
convert that to `.tflite`. Attempting this for a PyTorch result is
rejected up front with a clear error.

## 1. Register a device

In the **IoT Devices** tab, register a Tasmota device with its MQTT
connection details: friendly name, MQTT broker address/port, and
credentials. Kafka-ML generates a unique token for the device and a
ready-to-paste Tasmota **Backlog** command:

```
Backlog DeviceName <token>; FriendlyName <name>; MqttHost <host>; MqttPort <port>; MqttUser <user>; MqttPassword <password>; Topic <token>; FullTopic kafkaml/iot/%topic%/%prefix%/ ; MqttClient <token>; Hostname <token>; SetOption53 1
```

Run that once in the device's own web console (or over serial) to point
a freshly flashed Tasmota device at your MQTT broker and give it the
topic Kafka-ML will use to reach it.

## 2. Write the on-device inference script

Deploying a trained result to a device (from the **Results** list,
"Deploy on IoT" — only shown for TensorFlow results) asks for a
[Berry](https://github.com/berry-lang/berry) script, edited in the same
Monaco-based code editor used for model code elsewhere in the app (with
a real Berry — not Lua — syntax grammar). This script is what actually
runs on the device: reading sensor input, feeding it to the downloaded
`model.tflite`, and acting on the prediction. Select one or more
registered devices to deploy to, and optionally enable **INT8
quantization** — this shrinks the model further for constrained
hardware, at the cost of needing to sample real training data live from
Kafka for calibration first (up to ~60s).

## 3. What happens next

The backend converts the training result's `.h5` model to `.tflite`
(via `mlcode_executor/tfexecutor`), stores it alongside your Berry
script per device, then pushes a small bootstrap script to the device
itself over MQTT. That bootstrap script downloads both files from the
backend over HTTP, deletes any previous version, and restarts the
device — Tasmota's Berry engine automatically runs a file named
`autoexec.be` on every boot, which is exactly what your uploaded script
is saved as. From that restart onward, the device is running your
script against the newly deployed model, fully on its own.

## Prerequisites on the device

- Tasmota firmware built with Berry scripting support
  ([tasmota32-berry](https://tasmota.github.io/docs/Berry/) or
  equivalent).
- Enough flash to hold `model.tflite` + `autoexec.be`.
- Network reachability both ways: the device needs to reach the
  backend's HTTP API to download the files, and the backend needs to
  reach your MQTT broker to push the bootstrap command.
