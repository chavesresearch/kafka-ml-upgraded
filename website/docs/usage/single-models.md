---
sidebar_position: 1
---

# Single Models

The golden path: define a model, deploy it for training, stream data
through Kafka, watch the metrics, then deploy the trained model for
real-time inference.

To follow this tutorial, deploy Kafka-ML as shown in [Getting
Started](../getting-started).

## 1. Define an ML/AI model

Create a model in the **Models** tab with just TF/Keras model source
code, and imports/functions if needed. This model for the MNIST dataset
is a simple way to start:

```py
model = tf.keras.models.Sequential([
  tf.keras.layers.Flatten(input_shape=(28, 28)),
  tf.keras.layers.Dense(128, activation='relu'),
  tf.keras.layers.Dense(10, activation='softmax')
])
model.compile(
    optimizer=tf.keras.optimizers.Adam(0.001),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=[tf.keras.metrics.SparseCategoricalAccuracy()],
)
```

Something similar for PyTorch:

```py
class NeuralNetwork(nn.Module):
    def __init__(self):
        super(NeuralNetwork, self).__init__()
        self.flatten = nn.Flatten()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(28*28, 128),
            nn.ReLU(),
            nn.Linear(128, 10),
            nn.Softmax()
        )

    def forward(self, x):
        x = self.flatten(x)
        logits = self.linear_relu_stack(x)
        return logits

    def loss_fn(self):
        return nn.CrossEntropyLoss()

    def optimizer(self):
        return torch.optim.Adam(model.parameters(), lr=0.001)

    def metrics(self):
        return {"accuracy": Accuracy(), "loss": Loss(self.loss_fn())}

model = NeuralNetwork()
```

`loss_fn`, `optimizer`, and `metrics` must always be defined for PyTorch
models.

![Create a TensorFlow model](/img/docs/create-model-tensorflow.svg)
<br/>
![Create a PyTorch model](/img/docs/create-model-pytorch.svg)

## 2. Define a configuration

A configuration is a set of models grouped for training — useful to
compare metrics across several models, or just to train one model with a
given data stream. A configuration can also contain a single model.

![Create a configuration](/img/docs/create-configuration.svg)

## 3. Deploy a configuration for training

![Deploy a configuration](/img/docs/deploy-configuration.png)

Set batch size and training/validation parameters using the same format
as TensorFlow's `fit`/`evaluate`. Validation parameters are optional —
they only apply if `validation_rate > 0` or `test_rate > 0` in the
stream received.

:::note
If your GPU(s) aren't tuned, **set "GPU Memory usage estimation" to 0** —
otherwise the training component deploys but stays pending, waiting to
allocate GPU memory (`kubectl describe` will show an `aliyun.com/gpu-mem`
warning). You can also enable confusion-matrix generation at the end of
training.
:::

![Configure a deployment](/img/docs/configure-deployment.svg)

Once deployed, you'll see one training result per model in the
configuration — ready to receive stream data.

![Training results](/img/docs/training-results.png)

## 4. Stream data for training

If you used the MNIST model above, use the bundled example:

```sh
python examples/MNIST_RAW_format/mnist_dataset_training_example.py
```

Set its `deployment_id` to the one Kafka-ML generated (often `1`) — this
is how a data stream is matched to a configuration/model during
training. You may need `datasources/requirements.txt`'s libraries
installed first. For your own data, use `kafkaml_datasources`' `AvroSink`
(Apache Avro) or `RawSink` (simple types) — see the [SDK
docs](/sdk/intro) for the Python client that wraps the same API these
examples call directly.

## 5. Model metrics visualization

Once data has been streamed and the model trained, you'll see its
metrics and results in Kafka-ML — download the trained model, or
continue to deploy it for inference.

![Training metrics](/img/docs/training-metrics.svg)

To see the confusion matrix (if enabled) or per-epoch training/validation
metrics, open a training result's detail view:

![Plot view](/img/docs/plot-view.svg)

That view also exposes the same data as JSON, for building your own
plots and reports.

Once you have two or more finished results, see [Comparing Training
Results](./comparing-results) to overlay their metric curves side by
side.

## 6. Deploy a trained model for inference

TensorFlow models can also be deployed straight to a physical IoT
device instead of a Kubernetes inference pod — see [IoT / TFLite
Deployment](./iot-tflite-deployment).

Already have a trained model from outside Kafka-ML? See [Importing a
Trained Model](./importing-a-trained-model) to skip training entirely
and go straight to a deployable result.

Input-stream parameters are pre-filled from the training data seen
earlier (you can still change them). Mainly you'll set the number of
inference replicas and the input/output Kafka topics.

:::note
Same GPU caveat as training — **set "GPU Memory usage estimation" to 0**
if your GPU(s) aren't tuned, or the pod stays pending.
:::

![Deploy for inference](/img/docs/deploy-inference.svg)

## 7. Stream data for inference

```sh
python examples/MNIST_RAW_format/mnist_dataset_inference_example.py
```

## 8. Prediction visualization

In the Visualization tab, configure how prediction data should be
rendered. Example for MNIST:

```json
{
  "average_updated": false,
  "average_window": 10000,
  "type": "classification",
  "labels": [
    {"id": 0, "color": "#fff100", "label": "Zero"},
    {"id": 1, "color": "#ff8c00", "label": "One"},
    {"id": 2, "color": "#e81123", "label": "Two"},
    {"id": 3, "color": "#ec008c", "label": "Three"},
    {"id": 4, "color": "#68217a", "label": "Four"},
    {"id": 5, "color": "#00188f", "label": "Five"},
    {"id": 6, "color": "#00bcf2", "label": "Six"},
    {"id": 7, "color": "#00b294", "label": "Seven"},
    {"id": 8, "color": "#009e49", "label": "Eight"},
    {"id": 9, "color": "#bad80a", "label": "Nine"}
  ]
}
```

Two visualization types are supported: `regression` and `classification`.
In classification mode, `average_updated` toggles displaying the current
status based on the higher rolling average, and `average_window` sets
the averaging window.

Each model output needs a `label` entry: `id` is the output's position,
`color`/`label` control how it's displayed. Finally, set the output
topic the model is deployed on (`mnist-out` in the example above) and
the visualization starts showing your data.

Classification example:

![Classification visualization](/img/docs/classification.png)

Regression example:

![Regression visualization](/img/docs/regression.png)
