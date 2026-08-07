import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { getConfiguration, getFrameworksInConfiguration, getDistributedConfiguration, deploy } from '@/api'
import { enableFederatedBlockchain } from '@/env'
import { useNotify } from '@/notify'
import {
  KWARGS_RE,
  showIndefinite as showIndefiniteFn,
  showBlockchainToggle as showBlockchainToggleFn,
  showIndefiniteFields as showIndefiniteFieldsFn,
  isDeploymentFormInvalid,
  buildDeploymentPayload,
  type DeploymentForm,
} from '@/logic/deployment'
import type { Configuration } from '@/types'

const strategies = [{ value: 'FedAvg', label: 'Federated Averaging strategy' }]

const initialForm: DeploymentForm = {
  unsupervised: false,
  incremental: false,
  federated: false,
  indefinite: false,
  blockchain: false,
  batch: null,
  tf_kwargs_fit: '',
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
  gpumem: null,
  agg_rounds: null,
  min_data: null,
  data_restriction: '',
  agg_strategy: null,
  conf_mat_settings: false,
}

function numberOrNull(v: string): number | null {
  if (v === '') return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

export default function DeploymentView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()

  const configurationID = Number(id)
  const [configuration, setConfiguration] = useState<Partial<Configuration>>({})
  const [valid, setValid] = useState(false)
  const [detectedFrameworks, setDetectedFrameworks] = useState<string[]>([])
  const [showDistributed, setShowDistributed] = useState(false)
  const [form, setForm] = useState<DeploymentForm>(initialForm)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const config = await getConfiguration(configurationID)
        if (cancelled) return
        setConfiguration(config)
        setValid(true)
        const frameworks = await getFrameworksInConfiguration(configurationID)
        if (cancelled) return
        setDetectedFrameworks(frameworks)
        const distributed = await getDistributedConfiguration(configurationID)
        if (!cancelled) setShowDistributed(Boolean(distributed))
      } catch {
        if (!cancelled) notify.error('Configuration not found')
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configurationID])

  const hasTf = detectedFrameworks.includes('tf')
  const hasPth = detectedFrameworks.includes('pth')
  const showIndefinite = showIndefiniteFn(form)
  const showBlockchainToggle = showBlockchainToggleFn(form, enableFederatedBlockchain)
  const showIndefiniteFields = showIndefiniteFieldsFn(form)

  const tfKwargsFitInvalid = hasTf && !KWARGS_RE.test(form.tf_kwargs_fit || '')
  const tfKwargsValInvalid = hasTf && !KWARGS_RE.test(form.tf_kwargs_val || '')

  const formInvalid = isDeploymentFormInvalid(form, { detectedFrameworks, hasTf, hasPth })

  function set<K extends keyof DeploymentForm>(key: K, value: DeploymentForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload = buildDeploymentPayload(form, {
      configurationID,
      showDistributed,
      enableFederatedBlockchain,
    })
    try {
      await deploy(payload)
      navigate('/deployments')
    } catch (err) {
      notify.error('Error deploying the configuration: ' + (err as Error).message)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Deploy configuration {configuration.name}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
            <label className="flex items-center gap-2 text-sm font-normal">
              <Checkbox
                checked={form.unsupervised}
                onCheckedChange={(v) => set('unsupervised', v === true)}
              />
              Semi-supervised training
            </label>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm font-normal">
                <Checkbox checked={form.incremental} onCheckedChange={(v) => set('incremental', v === true)} />
                Incremental training
              </label>
              {!hasPth && (
                <label className="flex items-center gap-2 text-sm font-normal">
                  <Checkbox checked={form.federated} onCheckedChange={(v) => set('federated', v === true)} />
                  Federated learning
                </label>
              )}
            </div>
            {showIndefinite && (
              <label className="flex items-center gap-2 text-sm font-normal">
                <Checkbox checked={form.indefinite} onCheckedChange={(v) => set('indefinite', v === true)} />
                Indefinite training
              </label>
            )}
            {showBlockchainToggle && (
              <label className="flex items-center gap-2 text-sm font-normal">
                <Checkbox checked={form.blockchain} onCheckedChange={(v) => set('blockchain', v === true)} />
                Blockchain-traced training
              </label>
            )}

            <Separator />
            <h4 className="font-semibold">Model training settings</h4>

            {detectedFrameworks.length > 0 && (
              <div className="space-y-1.5">
                <Label>Batch size for training *</Label>
                <Input
                  type="number"
                  placeholder="10"
                  value={form.batch ?? ''}
                  onChange={(e) => set('batch', numberOrNull(e.target.value))}
                />
              </div>
            )}

            {hasTf && (
              <>
                <div className="space-y-1.5">
                  <Label>TensorFlow Training configuration *</Label>
                  <Input
                    placeholder="epochs=5"
                    value={form.tf_kwargs_fit}
                    onChange={(e) => set('tf_kwargs_fit', e.target.value)}
                  />
                  {form.tf_kwargs_fit && tfKwargsFitInvalid && (
                    <p className="text-sm text-destructive">Use the format: key=value, key=value</p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label>TensorFlow Validation configuration</Label>
                  <Input value={form.tf_kwargs_val} onChange={(e) => set('tf_kwargs_val', e.target.value)} />
                  {form.tf_kwargs_val && tfKwargsValInvalid && (
                    <p className="text-sm text-destructive">Use the format: key=value, key=value</p>
                  )}
                </div>
              </>
            )}

            {hasPth && (
              <>
                <div className="space-y-1.5">
                  <Label>PyTorch Training configuration *</Label>
                  <Input
                    placeholder="max_epochs=5"
                    value={form.pth_kwargs_fit}
                    onChange={(e) => set('pth_kwargs_fit', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>PyTorch Validation configuration</Label>
                  <Input value={form.pth_kwargs_val} onChange={(e) => set('pth_kwargs_val', e.target.value)} />
                </div>
              </>
            )}

            {form.unsupervised && (
              <>
                <Separator />
                <h4 className="font-semibold">Unsupervised models settings</h4>
                {!form.incremental && (
                  <div className="space-y-1.5">
                    <Label>Unsupervised rounds</Label>
                    <Input
                      type="number"
                      placeholder="5"
                      value={form.unsupervised_rounds ?? ''}
                      onChange={(e) => set('unsupervised_rounds', numberOrNull(e.target.value))}
                    />
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label>Confidence</Label>
                  <Input
                    type="number"
                    step="0.00001"
                    placeholder="0.9"
                    value={form.confidence ?? ''}
                    onChange={(e) => set('confidence', numberOrNull(e.target.value))}
                  />
                </div>
              </>
            )}

            {showDistributed && (
              <>
                <Separator />
                <h4 className="font-semibold">Distributed models settings</h4>
                <div className="space-y-1.5">
                  <Label>Optimizer</Label>
                  <Input placeholder="adam" value={form.optimizer} onChange={(e) => set('optimizer', e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Learning rate</Label>
                  <Input
                    placeholder="0.001"
                    value={form.learning_rate ?? ''}
                    onChange={(e) => set('learning_rate', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Loss function</Label>
                  <Input
                    placeholder="sparse_categorical_crossentropy"
                    value={form.loss}
                    onChange={(e) => set('loss', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Metrics (splitted by comas)</Label>
                  <Input
                    placeholder="sparse_categorical_accuracy"
                    value={form.metrics}
                    onChange={(e) => set('metrics', e.target.value)}
                  />
                </div>
              </>
            )}

            {form.incremental && (
              <>
                <Separator />
                <h4 className="font-semibold">Incremental training settings</h4>
                {!form.indefinite && (
                  <div className="space-y-1.5">
                    <Label>Stream timeout (in milliseconds)</Label>
                    <Input
                      type="number"
                      placeholder="60000"
                      value={form.stream_timeout ?? ''}
                      onChange={(e) => set('stream_timeout', numberOrNull(e.target.value))}
                    />
                  </div>
                )}
                {showIndefiniteFields && (
                  <>
                    <div className="space-y-1.5">
                      <Label>Monitoring metric (must match with a predefined metric) *</Label>
                      <Input value={form.monitoring_metric} onChange={(e) => set('monitoring_metric', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label>If the monitoring metric improves, does it increase or decrease? *</Label>
                      <RadioGroup
                        value={form.change}
                        onValueChange={(v) => set('change', v as DeploymentForm['change'])}
                        className="flex gap-6"
                      >
                        <label className="flex items-center gap-2 text-sm font-normal">
                          <RadioGroupItem value="up" /> Increase
                        </label>
                        <label className="flex items-center gap-2 text-sm font-normal">
                          <RadioGroupItem value="down" /> Decrease
                        </label>
                      </RadioGroup>
                    </div>
                    <div className="space-y-1.5">
                      <Label>Improvement</Label>
                      <Input
                        placeholder="0.05"
                        value={form.improvement ?? ''}
                        onChange={(e) => set('improvement', e.target.value)}
                      />
                    </div>
                  </>
                )}
              </>
            )}

            {detectedFrameworks.length > 0 && (
              <div className="space-y-1.5">
                <Label>GPU Memory usage estimation in GB (Kubernetes Scheduler) *</Label>
                <Input
                  type="number"
                  placeholder="0"
                  value={form.gpumem ?? ''}
                  onChange={(e) => set('gpumem', numberOrNull(e.target.value))}
                />
              </div>
            )}

            {form.federated && (
              <>
                <Separator />
                <h4 className="font-semibold">Federated strategy settings</h4>
                <div className="space-y-1.5">
                  <Label>Number of aggregation rounds *</Label>
                  <Input
                    type="number"
                    placeholder="15"
                    value={form.agg_rounds ?? ''}
                    onChange={(e) => set('agg_rounds', numberOrNull(e.target.value))}
                  />
                </div>
                {!form.incremental && (
                  <div className="space-y-1.5">
                    <Label>Minimun data entries per device *</Label>
                    <Input
                      type="number"
                      placeholder="1000"
                      value={form.min_data ?? ''}
                      onChange={(e) => set('min_data', numberOrNull(e.target.value))}
                    />
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label>Data Restriction *</Label>
                  <Input placeholder="{}" value={form.data_restriction} onChange={(e) => set('data_restriction', e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Aggregation strategy *</Label>
                  <Select value={form.agg_strategy ?? undefined} onValueChange={(v) => set('agg_strategy', v)}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select a strategy" />
                    </SelectTrigger>
                    <SelectContent>
                      {strategies.map((s) => (
                        <SelectItem key={s.value} value={s.value}>
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            {detectedFrameworks.length > 0 && !form.incremental && !form.federated && (
              <label className="flex items-center gap-2 text-sm font-normal">
                <Switch checked={form.conf_mat_settings} onCheckedChange={(v) => set('conf_mat_settings', v)} />
                Create confusion matrix at end (if test set is specified)
              </label>
            )}

            <div className="flex justify-between border-t pt-4">
              <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
                Go Back
              </Button>
              {valid && (
                <Button type="submit" disabled={formInvalid}>
                  Deploy
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
