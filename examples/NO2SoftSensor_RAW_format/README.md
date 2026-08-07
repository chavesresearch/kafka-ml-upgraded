# River Water Quality Monitoring Dataset Example

This example uses the [River Water Quality Monitoring 1990 to 2018](https://data.europa.eu/data/datasets/river-water-quality-monitoring-1990-to-2018?locale=es) dataset in Kafka-ML with a TensorFlow deep learning model.

```python
model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(128, input_shape=(4,), activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1),
      ])
model.compile(optimizer='adam', loss='huber', metrics=['mae', 'mape', 'mse'])
```

The batch_size used is 16 and the training configuration (epochs=32, shuffle=True).

In the PyTorch Case, the following deep learning model has been used in Kafka-ML for the River Water Quality dataset example:

```py
class NeuralNetwork(nn.Module):
    def __init__(self):
        super(NeuralNetwork, self).__init__()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(4, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        return self.linear_relu_stack(x)

    def loss_fn(self):
        return nn.HuberLoss()

    def optimizer(self):
        return torch.optim.Adam(model.parameters(), lr=1e-3)

    def metrics(self):
        val_metrics = {
            "mse": MeanSquaredError(),
            "loss": Loss(self.loss_fn())
         }
        return val_metrics

model = NeuralNetwork()
```
The batch_size used is 16 and the training configuration (max_epochs=32, shuffle=True).