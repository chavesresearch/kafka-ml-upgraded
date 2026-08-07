// REST client for the Kafka-ML backend.
// One function per endpoint, grouped by resource. Paths are identical to the
// ones the Angular frontend used (see frontend/src/app/services/*).
import { baseUrl } from './env'
import type {
  MLModel,
  ModelPayload,
  Configuration,
  ConfigurationPayload,
  DeploymentInfo,
  TrainingResult,
  Inference,
  InferenceDefaults,
  InferencePayload,
  IoTInferencePayload,
  Datasource,
  IoTDevice,
  IoTDevicePayload,
  ChartInfo
} from './types'
import type { DeploymentPayload } from './logic/deployment'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const options: RequestInit = { method, headers: {} }
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' }
    options.body = JSON.stringify(body)
  }
  const res = await fetch(baseUrl + path, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  const contentType = res.headers.get('Content-Type') || ''
  if (contentType.includes('application/json')) return res.json() as Promise<T>
  return res.text() as unknown as T
}

const get = <T>(path: string) => request<T>('GET', path)
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body)
const put = <T>(path: string, body?: unknown) => request<T>('PUT', path, body)
const del = <T>(path: string) => request<T>('DELETE', path)

// Fetch a binary endpoint; resolves to {blob, headers}.
async function getBlob(path: string): Promise<{ blob: Blob; headers: Headers }> {
  const res = await fetch(baseUrl + path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return { blob: await res.blob(), headers: res.headers }
}

/* Models */
export const getModels = () => get<MLModel[]>('/models/')
export const getDistributedModels = () => get<MLModel[]>('/models/distributed')
export const getFatherModels = () => get<MLModel[]>('/models/fathers')
export const getModel = (id: number) => get<MLModel>(`/models/${id}`)
export const getModelByResultId = (id: number) => get<MLModel>(`/models/result/${id}`)
export const createModel = (data: ModelPayload) => post<unknown>('/models/', data)
export const editModel = (id: number, data: ModelPayload) => put<unknown>(`/models/${id}`, data)
export const deleteModel = (id: number) => del<unknown>(`/models/${id}`)

/* Configurations */
export const getConfigurations = () => get<Configuration[]>('/configurations/')
export const getConfiguration = (id: number) => get<Configuration>(`/configurations/${id}`)
export const createConfiguration = (data: ConfigurationPayload) =>
  post<unknown>('/configurations/', data)
export const editConfiguration = (id: number, data: ConfigurationPayload) =>
  put<unknown>(`/configurations/${id}`, data)
export const deleteConfiguration = (id: number) => del<unknown>(`/configurations/${id}`)
export const getFrameworksInConfiguration = (id: number) =>
  get<string[]>(`/frameworksInConfiguration/${id}`)
export const getDistributedConfiguration = (id: number) =>
  get<boolean>(`/distributedConfiguration/${id}`)

/* Deployments */
export const getDeployments = () => get<DeploymentInfo[]>('/deployments/')
export const getDeploymentsOfConfiguration = (id: number) =>
  get<DeploymentInfo[]>(`/deployments/${id}`)
export const deploy = (data: DeploymentPayload) => post<unknown>('/deployments/', data)
export const deleteDeployment = (id: number) => del<unknown>(`/deployments/${id}`)

export interface ImportDeploymentMetrics {
  train_metrics?: Record<string, number[]>
  val_metrics?: Record<string, number[]>
  test_metrics?: Record<string, number[]>
  training_time?: number
}

// Not JSON like every other write here - a real .h5/.pth file has to go
// as multipart/form-data, so this bypasses the shared post() helper
// (which always JSON-encodes) and builds the request directly.
export async function importDeployment(
  configurationId: number,
  trainedModel: File,
  metrics?: ImportDeploymentMetrics
): Promise<void> {
  const form = new FormData()
  form.append('configuration', String(configurationId))
  form.append('trained_model', trainedModel)
  if (metrics) form.append('metrics', JSON.stringify(metrics))

  const res = await fetch(baseUrl + '/deployments/import', { method: 'POST', body: form })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
}

/* Training results */
export const getResults = () => get<TrainingResult[]>('/results/')
export const getResultsOfDeployment = (id: number) =>
  get<TrainingResult[]>(`/deployments/results/${id}`)
export const deleteResult = (id: number) => del<unknown>(`/results/${id}`)
export const stopTraining = (id: number) => post<unknown>(`/results/stop/${id}`)
export const getTrainedModel = (id: number) => getBlob(`/results/model/${id}`)
export const getConfusionMatrix = (id: number) => getBlob(`/results/confusion_matrix/${id}`)
export const getInferenceInfo = (id: number) => get<InferenceDefaults>(`/results/inference/${id}`)
export const getChartInfo = (id: number) => get<ChartInfo>(`/results/chart/${id}`)
export const deployInference = (id: number, data: InferencePayload) =>
  post<unknown>(`/results/inference/${id}`, data)
export const deployIoTInference = (id: number, data: IoTInferencePayload) =>
  post<unknown>(`/results/inference-iot/${id}`, data)

/* Inferences */
export const getInferences = () => get<Inference[]>('/inferences/')
export const stopInference = (id: number) => post<unknown>(`/inferences/${id}`)
export const deleteInference = (id: number) => del<unknown>(`/inferences/${id}`)

/* Datasources */
export const getDatasources = () => get<Datasource[]>('/datasources/')
export const deployDatasource = (data: Datasource) => post<unknown>('/datasources/kafka', data)

/* IoT devices */
export const getIoTDevices = () => get<IoTDevice[]>('/iot-devices/')
export const getIoTDevice = (id: number) => get<IoTDevice>(`/iot-devices/${id}`)
export const createIoTDevice = (data: IoTDevicePayload) => post<unknown>('/iot-devices/', data)
export const editIoTDevice = (id: number, data: IoTDevicePayload) =>
  put<unknown>(`/iot-devices/${id}`, data)
export const deleteIoTDevice = (id: number) => del<unknown>(`/iot-devices/${id}`)

// Trigger a browser download of a Blob.
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

// Download any JS value as a JSON file.
export function downloadJSON(data: unknown, filename: string): void {
  downloadBlob(new Blob([JSON.stringify(data)], { type: 'text/json' }), filename)
}
