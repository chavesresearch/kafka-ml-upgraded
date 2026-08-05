// The 9 real training modes, driven by the `CASE` env var (1-9) in
// model_training/tensorflow/utils.py + training.py, and by
// backend/app/controllers/deployments.py's dispatch logic
// (`5 if not deployment.blockchain else 9`). Semi-supervised learning is
// an orthogonal deployment flag (`unsupervised`), not a 10th case - see
// docs/usage/semi-supervised-learning - so this stays at exactly 9
// entries matching the real dispatch table.

export type CaseGroup = 'Single' | 'Distributed' | 'Federated';

// Drives how ResultsPanel renders each case's simulated metrics - kept
// distinct per case family so the chart itself communicates *how* that
// mode actually reports results, not just a generic accuracy/loss line:
//  - 'bounded': one fixed-size training run, x-axis "Epoch".
//  - 'streaming': never "finishes" - the chart keeps scrolling forward
//    live, matching incremental training's unbounded stream.
//  - 'federated': points land at irregular real-time intervals (not a
//    fixed tick), each annotated with which device it came from -
//    matching the real async, first-arrival-wins aggregation loop (see
//    useAsyncFederation's comment for the source).
export type ChartKind = 'bounded' | 'streaming' | 'federated';

export interface MetricsProfile {
  kind: ChartKind;
  metricName: string;
  numPoints: number;
  seed: number;
  xLabel: string;
  /** Render two series (Edge/Cloud submodel) instead of one. */
  distributed?: boolean;
  /** Show a per-round ERC-20 reward bar chart beneath the metric chart. */
  rewards?: boolean;
}

export interface CaseDefinition {
  id: number;
  slug: string;
  title: string;
  group: CaseGroup;
  summary: string;
  docsLink: string;
  modelCode: string;
  sdkSnippet: string;
  metrics: MetricsProfile;
}

const SINGLE_MODEL_CODE = `model = tf.keras.Sequential([
    tf.keras.layers.Input((1,)),
    tf.keras.layers.Dense(10, activation="relu"),
    tf.keras.layers.Dense(2, activation="softmax")
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])`;

const CLOUD_MODEL_CODE = `cloud_input = tf.keras.Input(shape=(4,), name="cloud_input")
x = tf.keras.layers.Dense(8, activation="relu")(cloud_input)
cloud_output = tf.keras.layers.Dense(2, activation="softmax", name="cloud_output")(x)
tf.keras.Model(inputs=cloud_input, outputs=cloud_output, name="cloud_model")`;

const EDGE_MODEL_CODE = `edge_input = tf.keras.Input(shape=(1,), name="edge_input")
x = tf.keras.layers.Dense(8, activation="relu")(edge_input)
output_to_cloud = tf.keras.layers.Dense(4, activation="relu", name="output_to_cloud")(x)
edge_output = tf.keras.layers.Dense(2, activation="softmax", name="edge_output")(x)
tf.keras.Model(inputs=[edge_input], outputs=[output_to_cloud, edge_output], name="edge_model")`;

export const caseDefinitions: CaseDefinition[] = [
  {
    id: 1,
    slug: 'single-classic',
    title: 'Single, Classic',
    group: 'Single',
    summary:
      'The golden path: one model, one training Job, trained once on a bounded data stream.',
    docsLink: '/docs/usage/single-models',
    modelCode: SINGLE_MODEL_CODE,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id,
    batch=4,
    tf_kwargs_fit="epochs=1",
)`,
    metrics: {kind: 'bounded', metricName: 'accuracy', numPoints: 10, seed: 1, xLabel: 'Epoch'},
  },
  {
    id: 2,
    slug: 'single-incremental',
    title: 'Single, Incremental',
    group: 'Single',
    summary:
      'The same single model, but trained continuously as new data streams in - no fixed dataset size.',
    docsLink: '/docs/usage/incremental-training',
    modelCode: SINGLE_MODEL_CODE,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id,
    batch=4,
    tf_kwargs_fit="epochs=1",
    incremental=True,
    stream_timeout=60000,
)`,
    metrics: {kind: 'streaming', metricName: 'accuracy', numPoints: 0, seed: 2, xLabel: 'Batch'},
  },
  {
    id: 3,
    slug: 'distributed',
    title: 'Distributed',
    group: 'Distributed',
    summary:
      'A father/child submodel chain (e.g. edge -> cloud) trained together as one hierarchy.',
    docsLink: '/docs/usage/distributed-models',
    modelCode: `${EDGE_MODEL_CODE}\n\n${CLOUD_MODEL_CODE}`,
    sdkSnippet: `edge_id = client.create_model("edge", EDGE_CODE, distributed=True)
cloud_id = client.create_model("cloud", CLOUD_CODE, distributed=True, father=edge_id)
config_id = client.create_configuration("chain", [edge_id])

deployment_id = client.create_deployment(
    configuration=config_id, batch=4,
    optimizer="adam", learning_rate=0.001,
    loss="sparse_categorical_crossentropy", metrics="accuracy",
)`,
    metrics: {kind: 'bounded', metricName: 'accuracy', numPoints: 10, seed: 3, xLabel: 'Epoch', distributed: true},
  },
  {
    id: 4,
    slug: 'distributed-incremental',
    title: 'Distributed + Incremental',
    group: 'Distributed',
    summary:
      'A distributed submodel chain, trained continuously as data streams in rather than on a fixed dataset.',
    docsLink: '/docs/usage/distributed-models',
    modelCode: `${EDGE_MODEL_CODE}\n\n${CLOUD_MODEL_CODE}`,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id, batch=4,
    optimizer="adam", loss="sparse_categorical_crossentropy", metrics="accuracy",
    incremental=True, stream_timeout=60000,
)`,
    metrics: {kind: 'streaming', metricName: 'accuracy', numPoints: 0, seed: 4, xLabel: 'Batch', distributed: true},
  },
  {
    id: 5,
    slug: 'federated',
    title: 'Federated',
    group: 'Federated',
    summary:
      'Edge devices train locally on their own data; the cloud aggregates updates with FedAvg. No raw data leaves the edge.',
    docsLink: '/docs/usage/federated-learning',
    modelCode: SINGLE_MODEL_CODE,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id, batch=4, tf_kwargs_fit="epochs=1",
    federated=True, agg_rounds=5, min_data=100, agg_strategy="FedAvg",
)`,
    metrics: {kind: 'federated', metricName: 'accuracy', numPoints: 8, seed: 5, xLabel: 'Round'},
  },
  {
    id: 6,
    slug: 'federated-incremental',
    title: 'Federated + Incremental',
    group: 'Federated',
    summary:
      'Federated rounds driven by a continuous streaming data source on each device, instead of a fixed local dataset.',
    docsLink: '/docs/usage/federated-learning',
    modelCode: SINGLE_MODEL_CODE,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id, batch=4, tf_kwargs_fit="epochs=1",
    federated=True, agg_rounds=5, min_data=5, agg_strategy="FedAvg",
    incremental=True, stream_timeout=30000,
)`,
    metrics: {kind: 'federated', metricName: 'accuracy', numPoints: 8, seed: 6, xLabel: 'Round'},
  },
  {
    id: 7,
    slug: 'federated-distributed',
    title: 'Federated + Distributed',
    group: 'Federated',
    summary:
      'Each edge device trains its own submodel chain locally; the cloud aggregates every submodel separately across devices.',
    docsLink: '/docs/usage/federated-learning',
    modelCode: `${EDGE_MODEL_CODE}\n\n${CLOUD_MODEL_CODE}`,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id, batch=4,
    optimizer="adam", loss="sparse_categorical_crossentropy", metrics="accuracy",
    federated=True, agg_rounds=5, min_data=100, agg_strategy="FedAvg",
)`,
    metrics: {kind: 'federated', metricName: 'accuracy', numPoints: 8, seed: 7, xLabel: 'Round', distributed: true},
  },
  {
    id: 8,
    slug: 'federated-distributed-incremental',
    title: 'Federated + Distributed + Incremental',
    group: 'Federated',
    summary:
      'Every mode combined: a distributed submodel chain, trained federatively, on a continuous streaming source per device.',
    docsLink: '/docs/usage/federated-learning',
    modelCode: `${EDGE_MODEL_CODE}\n\n${CLOUD_MODEL_CODE}`,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id, batch=4,
    optimizer="adam", loss="sparse_categorical_crossentropy", metrics="accuracy",
    federated=True, agg_rounds=5, min_data=5, agg_strategy="FedAvg",
    incremental=True, stream_timeout=30000,
)`,
    metrics: {kind: 'federated', metricName: 'accuracy', numPoints: 8, seed: 8, xLabel: 'Round', distributed: true},
  },
  {
    id: 9,
    slug: 'federated-blockchain',
    title: 'Federated + Blockchain',
    group: 'Federated',
    summary:
      'A federated round coordinated on-chain by a FederatedLearning smart contract, paying real ERC-20 rewards to participants by contribution.',
    docsLink: '/docs/usage/federated-learning',
    modelCode: SINGLE_MODEL_CODE,
    sdkSnippet: `deployment_id = client.create_deployment(
    configuration=config_id, batch=4, tf_kwargs_fit="epochs=1",
    federated=True, agg_rounds=3, min_data=10, agg_strategy="FedAvg",
    blockchain=True,
)`,
    metrics: {kind: 'federated', metricName: 'accuracy', numPoints: 8, seed: 9, xLabel: 'Round', rewards: true},
  },
];

export function getCaseBySlug(slug: string | null | undefined): CaseDefinition {
  return caseDefinitions.find((c) => c.slug === slug) ?? caseDefinitions[0];
}

export function getCaseById(id: number | null | undefined): CaseDefinition {
  return caseDefinitions.find((c) => c.id === id) ?? caseDefinitions[0];
}
