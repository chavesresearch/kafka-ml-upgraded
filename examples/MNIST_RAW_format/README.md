# MNIST

This is the example the root [README](../../README.md)'s own quickstart
walkthrough uses. The following TensorFlow deep learning model has been
used in Kafka-ML for this example using the MNIST dataset:

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

In the PyTorch Case, the following deep learning model has been used in
Kafka-ML for the MNIST dataset example:

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
        val_metrics = {
            "accuracy": Accuracy(),
            "loss": Loss(self.loss_fn())
         }
        return val_metrics

model = NeuralNetwork()
```

Note that functions `loss_fn`, `optimizer`, and `metrics` must necessarily
be defined - see the root README's ["Single models"](../../README.md#single-models)
section for the full walkthrough of pasting either model into the Web UI.

## Running this example

The data-producer scripts in this directory (`mnist_dataset_training_example.py`,
`mnist_dataset_inference_example.py`, and their online/unsupervised
variants) are framework-agnostic - they just stream raw MNIST
images/labels into Kafka via `kafkaml_datasources`' `RawSink`/`RawSource`
sinks, the same way regardless of which model (TensorFlow or PyTorch)
consumes them on the training/inference side. Deploy whichever model
above through the Web UI first, then run:

```sh
python examples/MNIST_RAW_format/mnist_dataset_training_example.py
```

setting `deployment_id` to the id Kafka-ML generated for your deployment.
Once trained, deploy the result for inference and run:

```sh
python examples/MNIST_RAW_format/mnist_dataset_inference_example.py
```

See `requirements.txt` for this example's own dependencies (only needed
for the TensorFlow-based scripts here that load `tf.keras.datasets.mnist`
directly to source the raw images - not a training-time dependency, since
the model itself, TF or PyTorch, is defined separately in the Web UI).
