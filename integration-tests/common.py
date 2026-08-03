"""Shared helpers for the Kafka-ML integration test suite.

Every test in this suite drives the *real* backend-litestar REST API
(create a model, a configuration, a deployment - the same calls the
frontend makes) via `kafkaml-client`, and sends *real* data over a *real*
Kafka broker, then polls for a real training/inference result. Nothing
here talks to the database directly or fabricates a Kubernetes Job by
hand - if the backend can't actually deploy a real Job against the real
cluster, these tests fail, which is the point.

Requires (see README.md): the local Docker Desktop Kubernetes cluster
with the `kafkaml` namespace running backend/kafka/tfexecutor/pthexecutor,
reachable directly at localhost:8000 / localhost:9094 (Docker Desktop's
LoadBalancer service type - see docker-desktop kafka-deployment.yaml's
`PLAINTEXT_HOST://localhost:9094` listener - no port-forward needed).
"""

from kafkaml_client import KafkaMLClient

BACKEND_URL = "http://localhost:8000"
BOOTSTRAP_SERVERS = "localhost:9094"

RETRY_TIMEOUT_S = 120
RETRY_INTERVAL_S = 2


def api_client() -> KafkaMLClient:
    return KafkaMLClient(BACKEND_URL, timeout=30)


def create_model(
    client: KafkaMLClient,
    name: str,
    code: str,
    framework: str = "tf",
    imports: str = "",
    distributed: bool = False,
    father: int | None = None,
) -> int:
    return client.create_model(
        name=name, code=code, framework=framework, imports=imports, distributed=distributed, father=father
    )


def create_configuration(client: KafkaMLClient, name: str, model_ids: list[int]) -> int:
    return client.create_configuration(name=name, model_ids=model_ids)


def create_deployment(client: KafkaMLClient, **fields) -> int:
    """Creates a deployment - this is the call that makes backend-litestar
    submit a real Kubernetes training Job. `fields` must include at least
    `configuration` (id) and `batch`; anything else (tf_kwargs_fit,
    incremental, federated, optimizer, ...) is passed straight through -
    see `KafkaMLClient.create_deployment`'s docstring for the full field
    reference."""
    return client.create_deployment(**fields)


def wait_for_status(
    client: KafkaMLClient,
    deployment_id: int,
    expected_status: str = "finished",
    timeout_s: int = RETRY_TIMEOUT_S,
    min_results: int = 1,
) -> list[dict]:
    return client.wait_for_results(
        deployment_id,
        status=expected_status,
        timeout=timeout_s,
        poll_interval=RETRY_INTERVAL_S,
        min_results=min_results,
    )


TF_SINGLE_MODEL_CODE = """model = tf.keras.Sequential([
    tf.keras.layers.Input((1,)),
    tf.keras.layers.Dense(10, activation="relu"),
    tf.keras.layers.Dense(2, activation="softmax")
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
"""
"""A minimal, real TF model: one float32 feature in, 2-class softmax out -
matches the RAW data shape `send_raw_data`/`send_online_raw_data` below
produce. Deliberately tiny, not a "real" model - this suite is testing the
platform's plumbing (API -> Job -> Kafka -> result), not model quality."""

# Distributed: same architecture split into two nodes as the
# model_training-upgraded/tensorflow test used, matching the README's
# edge/cloud pattern (see model_training-upgraded/tensorflow/CLAUDE.md's
# CASE=3 section) - the *cloud/root* node has no father, the *edge/child*
# node points at it. Note: distributed model code must end in a *bare*
# expression, no `model = ` prefix and no trailing newline - see
# mlcode_executor's `format_ml_code`, documented in
# model_training-upgraded/tensorflow/CLAUDE.md.
TF_CLOUD_MODEL_CODE = (
    'cloud_input = tf.keras.Input(shape=(4,), name="cloud_input")\n'
    'x = tf.keras.layers.Dense(8, activation="relu")(cloud_input)\n'
    'cloud_output = tf.keras.layers.Dense(2, activation="softmax", name="cloud_output")(x)\n'
    'tf.keras.Model(inputs=cloud_input, outputs=cloud_output, name="cloud_model")'
)
TF_EDGE_MODEL_CODE = (
    'edge_input = tf.keras.Input(shape=(1,), name="edge_input")\n'
    'x = tf.keras.layers.Dense(8, activation="relu")(edge_input)\n'
    'output_to_cloud = tf.keras.layers.Dense(4, activation="relu", name="output_to_cloud")(x)\n'
    'edge_output = tf.keras.layers.Dense(2, activation="softmax", name="edge_output")(x)\n'
    'tf.keras.Model(inputs=[edge_input], outputs=[output_to_cloud, edge_output], name="edge_model")'
)

PTH_MODEL_CODE = """class NeuralNetwork(nn.Module):
    def __init__(self):
        super(NeuralNetwork, self).__init__()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(1, 8),
            nn.ReLU(),
            nn.Linear(8, 2)
        )

    def forward(self, x):
        return self.linear_relu_stack(x)

    def loss_fn(self):
        ce = nn.CrossEntropyLoss()
        return lambda y_pred, y: ce(y_pred, y.long())

    def optimizer(self):
        return torch.optim.Adam(model.parameters(), lr=0.001)

    def metrics(self):
        return {
            "accuracy": Accuracy(),
            "loss": Loss(self.loss_fn())
        }

model = NeuralNetwork()
"""
