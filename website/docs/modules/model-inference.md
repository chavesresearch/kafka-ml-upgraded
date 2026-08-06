---
sidebar_position: 5
---

# model_inference

`model_inference` serves an already-trained `TrainingResult`: it consumes
a live input Kafka topic, runs each message through the model, and
produces the prediction to an output Kafka topic. Unlike `model_training`,
there is no `CASE` dispatch and no per-mode class hierarchy — each
framework has exactly one `inference.py`, a plain
`while True: consumer.poll(...)` loop built on `confluent_kafka`.

## ReplicationController, not Job

`model_training` runs as a Kubernetes **Job** — it has a clear
start/finish (a training run either completes or fails). Inference is a
standing service with no natural end, so `backend`'s
`POST /results/inference/{result_id}` (`backend/app/controllers/
inferences.py`, `deploy_inference`) instead creates a Kubernetes
**ReplicationController**:

```python
await api_instance.create_namespaced_replication_controller(
    body=manifest, namespace=settings.KUBE_NAMESPACE
)
```

`_single_inference_manifest`/`_distributed_inference_manifest` in that
same file build the manifest (`"kind": "ReplicationController"`),
choosing `settings.TENSORFLOW_INFERENCE_MODEL_IMAGE` or
`settings.PYTORCH_INFERENCE_MODEL_IMAGE` based on `result.model.framework`,
and setting `spec.replicas` from the request body's `replicas` field —
this is what makes an inference deployment horizontally scalable (each
replica pod is an independent consumer in the same Kafka consumer group,
`GROUP_ID = f"inf{result.id}"`), where a Job has no equivalent concept of
serving replicas. `POST /results/inference/{result_id}` deliberately
returns Litestar's default 201 (a new `Inference` DB row really is being
created), unlike most of `backend`'s other POST endpoints, which were
patched to return 200 to match `model_training`'s status-code contract.

## The consume → predict → produce loop

Both `inference.py` scripts follow the same shape:

```python
consumer = Consumer({'bootstrap.servers': input_bootstrap_servers,
                      'group.id': group_id,
                      'auto.offset.reset': 'earliest',
                      'enable.auto.commit': False})
consumer.subscribe([input_topic])
output_producer = Producer({'bootstrap.servers': output_bootstrap_servers})

while True:
  msg = consumer.poll(1.0)
  if msg is None or msg.error():
    continue
  input_decoded = decoder.decode(msg.value())
  prediction_output = model.predict(input_decoded)  # or model(x) for PyTorch
  response = {'values': prediction_output.tolist()[0]}
  output_producer.produce(output_topic, json.dumps(response).encode(),
                           headers=msg.headers())
  if commitedMessages >= MAX_MESSAGES_TO_COMMIT:
    consumer.commit()
```

Unlike training's control-topic handshake, there is no per-message
deployment-id filtering here — `INPUT_TOPIC`/`OUTPUT_TOPIC`/`GROUP_ID` are
fixed at deployment time via env vars on the ReplicationController's pod
template, so every message on the input topic is treated as inference
input. Offsets are committed in batches of `MAX_MESSAGES_TO_COMMIT = 16`
rather than after every message, and Kafka message headers are forwarded
from input to output (`headers=msg.headers()`) so a caller can correlate
a prediction with its source message.

Both `inference.py` implementations reuse the same `DecoderFactory`
pattern from `model_training` (`decoders.py` in each of
`model_inference/tensorflow/` and `model_inference/pytorch/`) — `RawDecoder`
(`np.frombuffer` + `string_to_numpy_type`) is the exercised path; the
`AVRO` branch exists on both sides but is unreachable dead code
(`AvroDecoder.decode(self, x, y)` expects two arguments but `inference.py`
calls `decoder.decode(msg.value())` with one — a pre-existing bug, not
introduced by the framework upgrades, and identical on both frameworks).

## Loading the trained model

- **TensorFlow** (`model_inference/tensorflow/inference.py`): downloads
  one file from `MODEL_URL` (`{BACKEND_URL}/results/model/{result_id}`,
  the full `.h5` file) and loads it with `keras.models.load_model()`
  (`utils.py`). Inference never calls `load_model()`'s Keras-3
  recompile-after-reload fix that `model_training` needs — `.predict()`
  never touches the optimizer, only `.fit()` does, so that gotcha does
  not apply here.
- **PyTorch** (`model_inference/pytorch/inference.py`): downloads
  **two** things — the model's architecture as raw Python source from
  `MODEL_ARCH_URL` (`{BACKEND_URL}/results/{result_id}`, `exec()`'d via
  `utils.py`'s `download_model()`, same `exec()`-into-`globals()`
  mechanism `model_training/pytorch` uses) and the trained weights from
  `MODEL_URL` (`{BACKEND_URL}/results/model/{result_id}`) via
  `download_weights()`, then `model.load_state_dict(torch.load(...))`.
  `backend`'s `_single_inference_manifest` sets both `MODEL_ARCH_URL` and
  `MODEL_URL` env vars specifically for this reason.

## Distributed inference (TensorFlow only)

When `result.model.distributed` is true, `backend` builds a different
manifest (`_distributed_inference_manifest`) with extra env vars
(`UPPER_BOOTSTRAP_SERVERS`, `OUTPUT_UPPER`, `LIMIT`). In `inference.py`,
this enables a `distributed` branch: `model.predict(input_decoded)`
returns a `(prediction_to_upper, prediction_output)` pair (each
non-terminal submodel in a distributed chain has exactly two outputs —
features to forward plus its own prediction), and the low-confidence
case forwards `prediction_to_upper` upstream instead of producing a final
answer:

```python
if distributed and max(prediction_value) < limit:
  upper_producer.produce(output_upper, prediction_to_upper.tobytes(), headers=msg.headers())
else:
  output_producer.produce(output_topic, response_to_kafka, headers=msg.headers())
```

This lets a low-confidence prediction at one submodel escalate to the
next ("upper") model in the chain rather than being served directly —
the same father/child chain concept used by `model_training`'s
distributed training modes (CASE 3/4/7/8), now applied at serving time.
There is no PyTorch equivalent of this branch.

## TensorFlow vs. PyTorch: summary of differences

| | TensorFlow | PyTorch |
|---|---|---|
| Model artifact(s) | one `.h5` file (`MODEL_URL`) | Python source (`MODEL_ARCH_URL`) + weights (`MODEL_URL`) |
| Prediction call | `model.predict(input_decoded)` | `model(tensored_input)` after wrapping with `torchvision.transforms.ToTensor()` + `torch.unsqueeze(..., 0)` |
| Distributed/upper-model forwarding | supported (`UPPER_BOOTSTRAP_SERVERS`/`OUTPUT_UPPER`/`LIMIT`) | not supported |
| Output shape | raw `model.predict()` output, `.tolist()[0]` | `ToTensor()` is written for image-shaped `(H, W, C)` input; a flat feature vector still runs but picks up extra shape padding along the way — a caller consuming PyTorch inference output for non-image data needs to account for this |
| GPU handling | `tf.config.experimental.list_physical_devices('GPU')` + memory growth | `torch.device("cuda" if torch.cuda.is_available() else "cpu")` |

## IoT / edge inference

`model_inference`'s own containers have no IoT-specific code path. Device
deployment (compiling a model to TFLite, generating a Tasmota/Berry
provisioning script, pushing the `.tflite` file to a device over MQTT) is
a separate feature implemented entirely in `backend`
(`app/controllers/iot_devices.py` — `download_iot_model`,
`download_iot_script`, `deploy_to_iot_devices`) and is unrelated to the
ReplicationController-based containers described on this page; an IoT
device runs the served model itself rather than talking to a
`model_inference` pod over Kafka.

## See also

- [`backend`](./backend) — owns `deploy_inference`/`stop_inference` and
  builds the ReplicationController manifests this module runs in.
- [`model_training`](./model-training) — produces the `TrainingResult`
  (model file/weights, architecture) that this module downloads and
  serves.
- [`datasources`](./datasources) — the client library used to publish
  data onto the input topic an inference deployment consumes.
