// Pure logic for the deployment form: payload building and validation.
// Extracted out of DeploymentView.vue so it can be unit tested without
// mounting the component (this is where the agg_strategy/strategy key bug
// was found, see CLAUDE.md).

export interface DeploymentForm {
  unsupervised: boolean
  incremental: boolean
  federated: boolean
  indefinite: boolean
  blockchain: boolean
  batch: number | null
  tf_kwargs_fit: string
  tf_kwargs_val: string
  pth_kwargs_fit: string
  pth_kwargs_val: string
  unsupervised_rounds: number | null
  confidence: number | null
  optimizer: string
  learning_rate: string | number | null
  loss: string
  metrics: string
  stream_timeout: number | null
  monitoring_metric: string
  change: '' | 'up' | 'down'
  improvement: string | number | null
  gpumem: number | null
  agg_rounds: number | null
  min_data: number | null
  data_restriction: string
  agg_strategy: string | null
  conf_mat_settings: boolean
}

export interface FrameworkContext {
  detectedFrameworks: string[]
  hasTf: boolean
  hasPth: boolean
}

export interface PayloadContext {
  configurationID: number
  showDistributed: boolean
  enableFederatedBlockchain: boolean
}

export interface DeploymentPayload {
  configuration: number
  batch: number | null
  gpumem: number | null
  tf_kwargs_fit: string
  tf_kwargs_val: string
  pth_kwargs_fit: string
  pth_kwargs_val: string
  unsupervised: boolean
  incremental: boolean
  federated: boolean
  indefinite?: boolean
  blockchain?: boolean
  conf_mat_settings?: boolean
  unsupervised_rounds?: number
  confidence?: number
  optimizer?: string
  learning_rate?: string | number
  loss?: string
  metrics?: string
  stream_timeout?: number
  monitoring_metric?: string
  change?: string
  improvement?: string | number
  agg_rounds?: number | null
  min_data?: number | null
  data_restriction?: string
  agg_strategy?: string | null
}

// kwargs must look like "epochs=5, steps_per_epoch=10".
export const KWARGS_RE =
  /^[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*(,[ ]*[A-Za-z0-9-_]*[ ]*=[ ]*[A-Za-z0-9-_]*[ ]*)*$/

export function showIndefinite(form: DeploymentForm): boolean {
  return form.incremental && !form.federated
}

export function showBlockchainToggle(
  form: DeploymentForm,
  enableFederatedBlockchain: boolean
): boolean {
  return form.federated && !form.incremental && enableFederatedBlockchain
}

export function showIndefiniteFields(form: DeploymentForm): boolean {
  return form.incremental && form.indefinite && !form.federated
}

export function isDeploymentFormInvalid(form: DeploymentForm, context: FrameworkContext): boolean {
  const { detectedFrameworks, hasTf, hasPth } = context
  if (detectedFrameworks.length === 0) return true
  if (form.batch == null || form.gpumem == null) return true
  if (hasTf && !form.tf_kwargs_fit) return true
  if (hasPth && !form.pth_kwargs_fit) return true
  if (hasTf && !KWARGS_RE.test(form.tf_kwargs_fit || '')) return true
  if (hasTf && form.tf_kwargs_val && !KWARGS_RE.test(form.tf_kwargs_val)) return true
  if (hasPth && !KWARGS_RE.test(form.pth_kwargs_fit || '')) return true
  if (hasPth && form.pth_kwargs_val && !KWARGS_RE.test(form.pth_kwargs_val)) return true
  if (showIndefiniteFields(form) && (!form.monitoring_metric || !form.change)) return true
  if (form.federated) {
    // PyTorch training has no CASE dispatch at all - federated_model_
    // training/pytorch doesn't exist at any layer (see FUTURE.md's
    // CASE_2_9_PLAN.md). A federated deployment including a PyTorch
    // model wouldn't error, it would silently run plain classic training
    // while backend still records the deployment as federated - reject
    // it here rather than let that happen.
    if (hasPth) return true
    if (form.agg_rounds == null || !form.data_restriction || !form.agg_strategy) return true
    if (!form.incremental && form.min_data == null) return true
  }
  return false
}

// Builds the payload the backend expects, dropping empty optional fields
// (mirrors clearEmptyOrNullFields() from the original Angular component).
export function buildDeploymentPayload(
  form: DeploymentForm,
  context: PayloadContext
): DeploymentPayload {
  const { configurationID, showDistributed, enableFederatedBlockchain } = context

  const payload: DeploymentPayload = {
    configuration: configurationID,
    batch: form.batch,
    gpumem: form.gpumem,
    tf_kwargs_fit: form.tf_kwargs_fit || '',
    tf_kwargs_val: form.tf_kwargs_val || '',
    pth_kwargs_fit: form.pth_kwargs_fit || '',
    pth_kwargs_val: form.pth_kwargs_val || '',
    unsupervised: form.unsupervised,
    incremental: form.incremental,
    federated: form.federated
  }

  if (showIndefinite(form)) payload.indefinite = form.indefinite
  if (showBlockchainToggle(form, enableFederatedBlockchain)) payload.blockchain = form.blockchain
  if (!form.incremental && !form.federated) payload.conf_mat_settings = form.conf_mat_settings

  if (form.unsupervised) {
    if (form.unsupervised_rounds != null && !form.incremental) {
      payload.unsupervised_rounds = form.unsupervised_rounds
    }
    if (form.confidence != null) payload.confidence = form.confidence
  }

  if (showDistributed) {
    if (form.optimizer) payload.optimizer = form.optimizer
    if (form.learning_rate !== '' && form.learning_rate != null) {
      payload.learning_rate = form.learning_rate
    }
    if (form.loss) payload.loss = form.loss
    if (form.metrics) payload.metrics = form.metrics
  }

  if (form.incremental) {
    if (!form.indefinite && form.stream_timeout != null) {
      payload.stream_timeout = form.stream_timeout
    }
    if (showIndefiniteFields(form)) {
      payload.monitoring_metric = form.monitoring_metric
      payload.change = form.change
      if (form.improvement !== '' && form.improvement != null) {
        payload.improvement = form.improvement
      }
    }
  }

  if (form.federated) {
    payload.agg_rounds = form.agg_rounds
    if (!form.incremental) payload.min_data = form.min_data
    payload.data_restriction = form.data_restriction
    // Must be "agg_strategy" (the backend serializer field name), not
    // "strategy" — the original Angular form got this wrong and the value
    // was silently dropped, always deploying with the backend default.
    payload.agg_strategy = form.agg_strategy
  }

  return payload
}
