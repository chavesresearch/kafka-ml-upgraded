import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { getInferenceInfo, getModelByResultId, deployInference } from '@/api'
import { useNotify } from '@/notify'
import type { InferencePayload } from '@/types'

interface FormState {
  replicas: number | null
  input_format: string
  input_config: string
  input_kafka_broker: string
  input_topic: string
  output_kafka_broker: string
  output_topic: string
  upper_kafka_broker: string
  output_upper: string
  external_host: string
  token: string
  limit: number | string
  gpumem: number | null
}

const emptyForm: FormState = {
  replicas: null,
  input_format: '',
  input_config: '',
  input_kafka_broker: '',
  input_topic: '',
  output_kafka_broker: '',
  output_topic: '',
  upper_kafka_broker: '',
  output_upper: '',
  external_host: '',
  token: '',
  limit: '',
  gpumem: null,
}

function numberOrNull(v: string): number | null {
  if (v === '') return null
  const n = Number(v)
  return Number.isNaN(n) ? null : n
}

export default function InferenceView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()

  const resultID = Number(id)
  const [valid, setValid] = useState(false)
  const [distributed, setDistributed] = useState(false)
  const [form, setForm] = useState<FormState>(emptyForm)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const info = await getInferenceInfo(resultID)
        if (cancelled) return
        if (info.input_format !== '') {
          setForm((f) => ({ ...f, input_format: info.input_format, input_config: info.input_config }))
          notify.ok('Input format and configuration found from another dataset/inference')
        }
        setValid(true)
      } catch {
        if (!cancelled) notify.error('The training result does not exist')
      }
      try {
        const model = await getModelByResultId(resultID)
        // Only sub-models below the top of a distributed chain forward partial predictions to an upper model.
        if (!cancelled) setDistributed(Boolean(model.distributed && model.father != null))
      } catch {
        if (!cancelled) {
          setValid(false)
          notify.error('Error model not found')
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultID])

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const formInvalid = (() => {
    if (form.replicas == null || !form.input_format || !form.input_config) return true
    if (!form.input_topic || !form.output_topic || form.gpumem == null) return true
    if (distributed && (!form.output_upper || form.limit === '')) return true
    return false
  })()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: InferencePayload = { ...form, model_result: resultID }
    if (!distributed) {
      delete payload.upper_kafka_broker
      delete payload.output_upper
      delete payload.limit
    }
    try {
      await deployInference(resultID, payload)
      notify.ok('Model deployed for inference')
      navigate('/inferences')
    } catch {
      notify.error('Error deploying the model for inference')
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Deploy Training result {resultID} for inference</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
            <div className="space-y-1.5">
              <Label>Number of replicas *</Label>
              <Input
                type="number"
                placeholder="1"
                value={form.replicas ?? ''}
                onChange={(e) => set('replicas', numberOrNull(e.target.value))}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Input format of data *</Label>
              <Input placeholder="RAW" value={form.input_format} onChange={(e) => set('input_format', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Configuration for input data *</Label>
              <Input
                placeholder='{"data_type": "", "label_type": "", "data_reshape": "", "label_reshape": ""}'
                value={form.input_config}
                onChange={(e) => set('input_config', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Kafka broker for input data</Label>
              <Input
                placeholder="Input kafka broker (e.g. https://192.168.65.3:9094)"
                value={form.input_kafka_broker}
                onChange={(e) => set('input_kafka_broker', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Kafka topic for input data *</Label>
              <Input placeholder="input_topic" value={form.input_topic} onChange={(e) => set('input_topic', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Kafka broker for output data</Label>
              <Input
                placeholder="Output kafka broker (e.g. https://192.168.65.3:9094)"
                value={form.output_kafka_broker}
                onChange={(e) => set('output_kafka_broker', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Kafka output topic for predictions *</Label>
              <Input placeholder="output_topic" value={form.output_topic} onChange={(e) => set('output_topic', e.target.value)} />
            </div>

            {distributed && (
              <>
                <div className="space-y-1.5">
                  <Label>Kafka broker for upper data</Label>
                  <Input
                    placeholder="Upper kafka broker (e.g. https://192.168.65.3:9094)"
                    value={form.upper_kafka_broker}
                    onChange={(e) => set('upper_kafka_broker', e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Kafka output topic for upper model *</Label>
                  <Input placeholder="output_upper" value={form.output_upper} onChange={(e) => set('output_upper', e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>Prediction limit *</Label>
                  <Input placeholder="limit" value={form.limit} onChange={(e) => set('limit', e.target.value)} />
                </div>
              </>
            )}

            <div className="space-y-1.5">
              <Label>Kubernetes Cluster Host</Label>
              <Input
                placeholder="External Host (e.g. https://192.168.65.3:6443)"
                value={form.external_host}
                onChange={(e) => set('external_host', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Kubernetes Cluster Token</Label>
              <Input placeholder="Token" value={form.token} onChange={(e) => set('token', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>GPU Memory usage estimation (Kubernetes Scheduler) *</Label>
              <Input
                type="number"
                placeholder="0"
                value={form.gpumem ?? ''}
                onChange={(e) => set('gpumem', numberOrNull(e.target.value))}
              />
            </div>

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
