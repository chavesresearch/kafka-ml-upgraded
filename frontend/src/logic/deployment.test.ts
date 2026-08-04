import { describe, it, expect } from 'vitest'
import {
  isDeploymentFormInvalid,
  buildDeploymentPayload,
  showIndefinite,
  showBlockchainToggle,
  showIndefiniteFields,
  type DeploymentForm
} from './deployment'

function baseForm(overrides: Partial<DeploymentForm> = {}): DeploymentForm {
  return {
    unsupervised: false,
    incremental: false,
    federated: false,
    indefinite: false,
    blockchain: false,
    batch: 10,
    tf_kwargs_fit: 'epochs=5',
    tf_kwargs_val: '',
    pth_kwargs_fit: '',
    pth_kwargs_val: '',
    unsupervised_rounds: null,
    confidence: null,
    optimizer: '',
    learning_rate: '',
    loss: '',
    metrics: '',
    stream_timeout: null,
    monitoring_metric: '',
    change: '',
    improvement: '',
    gpumem: 0,
    agg_rounds: null,
    min_data: null,
    data_restriction: '',
    agg_strategy: null,
    conf_mat_settings: false,
    ...overrides
  }
}

describe('isDeploymentFormInvalid', () => {
  it('is invalid when no frameworks were detected', () => {
    const form = baseForm()
    expect(isDeploymentFormInvalid(form, { detectedFrameworks: [], hasTf: false, hasPth: false })).toBe(
      true
    )
  })

  it('is valid for a plain TF deployment with batch/gpumem/kwargs set', () => {
    const form = baseForm()
    expect(
      isDeploymentFormInvalid(form, { detectedFrameworks: ['tf'], hasTf: true, hasPth: false })
    ).toBe(false)
  })

  it('rejects malformed tf_kwargs_fit', () => {
    const form = baseForm({ tf_kwargs_fit: 'epochs 5' })
    expect(
      isDeploymentFormInvalid(form, { detectedFrameworks: ['tf'], hasTf: true, hasPth: false })
    ).toBe(true)
  })

  it('accepts multi-key kwargs', () => {
    const form = baseForm({ tf_kwargs_fit: 'epochs=5, steps_per_epoch=10' })
    expect(
      isDeploymentFormInvalid(form, { detectedFrameworks: ['tf'], hasTf: true, hasPth: false })
    ).toBe(false)
  })

  it('requires monitoring_metric and change for indefinite incremental training', () => {
    const form = baseForm({ incremental: true, indefinite: true })
    const context = { detectedFrameworks: ['tf'], hasTf: true, hasPth: false }
    expect(isDeploymentFormInvalid(form, context)).toBe(true)

    form.monitoring_metric = 'val_accuracy'
    form.change = 'up'
    expect(isDeploymentFormInvalid(form, context)).toBe(false)
  })

  it('does not require monitoring_metric for time-limited (non-indefinite) incremental training', () => {
    const form = baseForm({ incremental: true, indefinite: false })
    expect(
      isDeploymentFormInvalid(form, { detectedFrameworks: ['tf'], hasTf: true, hasPth: false })
    ).toBe(false)
  })

  it('requires agg_rounds, data_restriction and agg_strategy for federated deployments', () => {
    const context = { detectedFrameworks: ['tf'], hasTf: true, hasPth: false }
    const incomplete = baseForm({ federated: true, agg_rounds: 15, min_data: 1000 })
    expect(isDeploymentFormInvalid(incomplete, context)).toBe(true)

    const complete = baseForm({
      federated: true,
      agg_rounds: 15,
      min_data: 1000,
      data_restriction: '{}',
      agg_strategy: 'FedAvg'
    })
    expect(isDeploymentFormInvalid(complete, context)).toBe(false)
  })

  it('does not require min_data for federated + incremental deployments', () => {
    const context = { detectedFrameworks: ['tf'], hasTf: true, hasPth: false }
    const form = baseForm({
      federated: true,
      incremental: true,
      agg_rounds: 15,
      data_restriction: '{}',
      agg_strategy: 'FedAvg'
    })
    expect(isDeploymentFormInvalid(form, context)).toBe(false)
  })

  it('requires pth_kwargs_fit when the configuration only has PyTorch models', () => {
    const context = { detectedFrameworks: ['pth'], hasTf: false, hasPth: true }
    expect(isDeploymentFormInvalid(baseForm({ tf_kwargs_fit: '' }), context)).toBe(true)
    expect(
      isDeploymentFormInvalid(baseForm({ tf_kwargs_fit: '', pth_kwargs_fit: 'max_epochs=5' }), context)
    ).toBe(false)
  })
})

describe('visibility helpers', () => {
  it('showIndefinite is true only for incremental, non-federated deployments', () => {
    expect(showIndefinite(baseForm({ incremental: true, federated: false }))).toBe(true)
    expect(showIndefinite(baseForm({ incremental: true, federated: true }))).toBe(false)
    expect(showIndefinite(baseForm({ incremental: false }))).toBe(false)
  })

  it('showBlockchainToggle requires federated + not incremental + feature flag', () => {
    const form = baseForm({ federated: true, incremental: false })
    expect(showBlockchainToggle(form, true)).toBe(true)
    expect(showBlockchainToggle(form, false)).toBe(false)
    expect(showBlockchainToggle(baseForm({ federated: true, incremental: true }), true)).toBe(false)
  })

  it('showIndefiniteFields requires incremental + indefinite + not federated', () => {
    expect(showIndefiniteFields(baseForm({ incremental: true, indefinite: true }))).toBe(true)
    expect(
      showIndefiniteFields(baseForm({ incremental: true, indefinite: true, federated: true }))
    ).toBe(false)
  })
})

describe('buildDeploymentPayload', () => {
  const distributedContext = { configurationID: 7, showDistributed: true, enableFederatedBlockchain: false }
  const plainContext = { configurationID: 7, showDistributed: false, enableFederatedBlockchain: false }

  it('builds a minimal payload for a plain deployment', () => {
    const payload = buildDeploymentPayload(baseForm(), plainContext)
    expect(payload).toMatchObject({
      configuration: 7,
      batch: 10,
      gpumem: 0,
      tf_kwargs_fit: 'epochs=5',
      unsupervised: false,
      incremental: false,
      federated: false,
      conf_mat_settings: false
    })
    // Optional fields for features that are off must not be sent at all.
    expect(payload).not.toHaveProperty('agg_strategy')
    expect(payload).not.toHaveProperty('monitoring_metric')
    expect(payload).not.toHaveProperty('indefinite')
  })

  it('sends agg_strategy (not "strategy") for federated deployments', () => {
    const form = baseForm({
      federated: true,
      agg_rounds: 15,
      min_data: 1000,
      data_restriction: '{}',
      agg_strategy: 'FedAvg'
    })
    const payload = buildDeploymentPayload(form, plainContext)
    expect(payload.agg_strategy).toBe('FedAvg')
    expect(payload).not.toHaveProperty('strategy')
    expect(payload.conf_mat_settings).toBeUndefined()
  })

  it('omits min_data for federated + incremental, keeps agg_rounds/data_restriction', () => {
    const form = baseForm({
      federated: true,
      incremental: true,
      agg_rounds: 15,
      data_restriction: '{}',
      agg_strategy: 'FedAvg'
    })
    const payload = buildDeploymentPayload(form, plainContext)
    expect(payload).not.toHaveProperty('min_data')
    expect(payload.agg_rounds).toBe(15)
  })

  it('includes distributed-model settings only when showDistributed is true', () => {
    const form = baseForm({ optimizer: 'adam', learning_rate: 0.001, loss: 'mse', metrics: 'accuracy' })
    expect(buildDeploymentPayload(form, plainContext)).not.toHaveProperty('optimizer')
    const payload = buildDeploymentPayload(form, distributedContext)
    expect(payload).toMatchObject({ optimizer: 'adam', learning_rate: 0.001, loss: 'mse', metrics: 'accuracy' })
  })

  it('includes indefinite/monitoring fields only for indefinite incremental deployments', () => {
    const form = baseForm({
      incremental: true,
      indefinite: true,
      monitoring_metric: 'val_loss',
      change: 'down',
      improvement: 0.05
    })
    const payload = buildDeploymentPayload(form, plainContext)
    expect(payload.indefinite).toBe(true)
    expect(payload.monitoring_metric).toBe('val_loss')
    expect(payload.change).toBe('down')
    expect(payload.improvement).toBe(0.05)
    expect(payload).not.toHaveProperty('stream_timeout')
  })

  it('sends stream_timeout for time-limited (non-indefinite) incremental deployments', () => {
    const form = baseForm({ incremental: true, indefinite: false, stream_timeout: 60000 })
    const payload = buildDeploymentPayload(form, plainContext)
    expect(payload.stream_timeout).toBe(60000)
    expect(payload).not.toHaveProperty('monitoring_metric')
  })

  it('includes blockchain flag only when the toggle is shown', () => {
    const form = baseForm({ federated: true, blockchain: true })
    expect(buildDeploymentPayload(form, plainContext)).not.toHaveProperty('blockchain')
    const blockchainContext = { ...plainContext, enableFederatedBlockchain: true }
    expect(buildDeploymentPayload(form, blockchainContext).blockchain).toBe(true)
  })

  it('includes unsupervised_rounds only when not incremental', () => {
    const form = baseForm({ unsupervised: true, unsupervised_rounds: 5, confidence: 0.9, incremental: true })
    const payload = buildDeploymentPayload(form, plainContext)
    expect(payload).not.toHaveProperty('unsupervised_rounds')
    expect(payload.confidence).toBe(0.9)
  })
})
