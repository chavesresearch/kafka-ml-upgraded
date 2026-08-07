// Shared shapes of the Kafka-ML backend's REST payloads.
// Field names mirror the Django serializers (backend/automl/serializers.py) —
// do not rename fields here without checking the backend first.

export interface SimpleModel {
  id: number
  name: string
  framework: Framework
}

export type Framework = 'tf' | 'pth'

export interface MLModel {
  id: number
  name: string
  description: string
  imports: string
  code: string
  distributed: boolean
  father: SimpleModel | null
  framework: Framework
}

export interface ModelPayload {
  name: string
  description: string
  framework: Framework | ''
  imports: string
  code: string
  distributed?: boolean
  father?: number
}

export interface Configuration {
  id: number
  name: string
  description: string
  ml_models: SimpleModel[]
  deployments?: { id: number; time: string }[]
}

export interface ConfigurationPayload {
  name: string
  description: string
  ml_models: number[]
}

export type TrainingStatus = 'created' | 'deployed' | 'stopped' | 'finished'

export interface TrainingResult {
  id: number
  status: TrainingStatus
  status_changed: string
  train_metrics: Record<string, number[]> | null
  val_metrics: Record<string, number[]> | null
  test_metrics: Record<string, number[]> | null
  training_time?: string | number | null
  model: SimpleModel
  deployment?: { id: number; time: string } | number
}

export interface DeploymentInfo {
  id: number
  time: string
  batch: number
  tf_kwargs_fit: string
  tf_kwargs_val: string
  pth_kwargs_fit: string
  pth_kwargs_val: string
  configuration: { id: number; name: string }
  results: TrainingResult[]
}

export interface Inference {
  id: number
  model_result: number
  replicas: number
  input_format: string
  input_config: string
  input_topic: string
  output_topic: string
  output_upper: string
  limit: number | string | null
  time: string
  status: 'deployed' | 'stopped'
  external_host: string
}

export interface InferenceDefaults {
  input_format: string
  input_config: string
}

export interface InferencePayload {
  replicas: number | null
  input_format: string
  input_config: string
  input_kafka_broker: string
  input_topic: string
  output_kafka_broker: string
  output_topic: string
  upper_kafka_broker?: string
  output_upper?: string
  limit?: number | string
  external_host: string
  token: string
  gpumem: number | null
  model_result: number
}

// Backend contract (backend/automl/views/iot_devices.py): keys are 'code',
// 'device_token', 'model_result', 'applyIntQuant'.
export interface IoTInferencePayload {
  code: string
  device_token: string[]
  model_result: number
  applyIntQuant: boolean
}

export interface Datasource {
  description: string
  deployment: string | number
  input_format: string
  input_config: string
  topic: string
  validation_rate: number
  test_rate: number
  total_msg: number
  time: string
}

export interface IoTDevice {
  id: number
  token: string
  friendly_name: string
  mqtt_address: string
  mqtt_port: number | string
  mqtt_username: string
  mqtt_password: string
  status: 'connected' | 'disconnected'
  backlog: string
}

export interface IoTDevicePayload {
  friendly_name: string
  mqtt_address: string
  mqtt_port: number | string
  mqtt_username: string
  mqtt_password: string
}

// GET /results/chart/{id} — metrics arrive in ngx-charts shape.
export interface ChartMetric {
  name: string
  series: { name: string | number; value: number }[]
}

export interface ChartInfo {
  metrics?: ChartMetric[] | null
  conf_mat?: unknown
}

// Minimal Chart.js data shapes we build (kept local instead of importing
// chart.js types — PrimeVue's Chart component takes them as plain objects).
export interface ChartDataset {
  label: string
  data: number[]
  borderColor?: string
  backgroundColor?: string | string[]
  fill?: boolean
  tension?: number
  pointRadius?: number
}

export interface ChartDataShape {
  labels: (string | number)[]
  datasets: ChartDataset[]
}
