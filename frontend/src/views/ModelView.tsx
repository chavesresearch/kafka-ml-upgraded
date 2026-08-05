import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import CodeEditor from '@/components/CodeEditor'
import { getModel, getDistributedModels, createModel, editModel } from '@/api'
import { useNotify } from '@/notify'
import type { Framework, ModelPayload, SimpleModel } from '@/types'

const TF_PLACEHOLDER = `model = tf.keras.models.Sequential([
  tf.keras.layers.Flatten(input_shape=(28, 28)),
  tf.keras.layers.Dense(128, activation='relu'),
  tf.keras.layers.Dense(10, activation='softmax')
])
model.compile(optimizer=tf.keras.optimizers.Adam(0.001),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=[tf.keras.metrics.SparseCategoricalAccuracy()])`

const PTH_PLACEHOLDER = `class NeuralNetwork(nn.Module):
    def __init__(self): ...
    def forward(self, x): ...
    def loss_fn(self): ...
    def optimizer(self): ...
    def metrics(self): ...

model = NeuralNetwork()`

interface FormState {
  name: string
  description: string
  framework: Framework | ''
  distributed: boolean
  father: number | null
  imports: string
  code: string
}

const emptyForm: FormState = {
  name: '',
  description: '',
  framework: '',
  distributed: false,
  father: null,
  imports: '',
  code: '',
}

export default function ModelView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()

  const modelId = id ? Number(id) : undefined
  const create = modelId === undefined
  const [valid, setValid] = useState(true)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [distributedModels, setDistributedModels] = useState<SimpleModel[]>([])

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!create && modelId !== undefined) {
        try {
          const model = await getModel(modelId)
          if (cancelled) return
          setForm({
            name: model.name,
            description: model.description,
            framework: model.framework,
            distributed: model.distributed,
            father: model.father ? model.father.id : null,
            imports: model.imports,
            code: model.code,
          })
        } catch {
          if (!cancelled) {
            setValid(false)
            notify.error('Error model not found')
          }
        }
      }
      try {
        const models = await getDistributedModels()
        if (!cancelled) setDistributedModels(models)
      } catch {
        if (!cancelled) notify.error('Error connecting with the server')
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelId])

  const placeholder = form.framework === 'tf' ? TF_PLACEHOLDER : form.framework === 'pth' ? PTH_PLACEHOLDER : ''
  const formInvalid = !form.name || !form.framework || !form.code

  function fatherName(fid: number | null): string {
    if (fid == null) return ''
    return distributedModels.find((m) => m.id === fid)?.name ?? ''
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const payload: ModelPayload = {
      name: form.name,
      description: form.description,
      framework: form.framework as Framework,
      imports: form.imports,
      code: form.code,
    }
    // Distributed models are a TensorFlow-only feature (same as the old frontend).
    if (form.framework === 'tf') {
      payload.distributed = form.distributed
      if (form.distributed && form.father != null) payload.father = form.father
    }
    try {
      if (create) {
        await createModel(payload)
        notify.ok('Model created')
      } else if (modelId !== undefined) {
        await editModel(modelId, payload)
        notify.ok('Model updated')
      }
      navigate('/models')
    } catch (err) {
      notify.error(`Error ${create ? 'creating' : 'updating'} the model: ` + (err as Error).message)
    }
  }

  const fatherOptions = useMemo(
    () => distributedModels.filter((m) => m.id !== modelId),
    [distributedModels, modelId],
  )

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>{create ? 'Create Model' : `Edit Model ${modelId}`}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                autoFocus
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label>Select ML Framework *</Label>
              <RadioGroup
                value={form.framework}
                onValueChange={(v) => setForm({ ...form, framework: v as Framework })}
                className="flex gap-6"
              >
                <label className="flex items-center gap-2 text-sm font-normal">
                  <RadioGroupItem value="tf" /> TensorFlow
                </label>
                <label className="flex items-center gap-2 text-sm font-normal">
                  <RadioGroupItem value="pth" /> PyTorch (Ignite)
                </label>
              </RadioGroup>
            </div>

            {form.framework === 'tf' && (
              <label className="flex items-center gap-2 text-sm font-normal">
                <Checkbox
                  checked={form.distributed}
                  onCheckedChange={(v) => setForm({ ...form, distributed: v === true })}
                />
                Distributed
              </label>
            )}

            {form.framework === 'tf' && form.distributed && (
              <div className="space-y-1.5">
                <Label>Upper model</Label>
                <Select
                  value={form.father != null ? String(form.father) : '__none__'}
                  onValueChange={(v) => setForm({ ...form, father: v === '__none__' ? null : Number(v) })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="None (top of the chain)">
                      {form.father != null ? `ID${form.father} ${fatherName(form.father)}` : 'None (top of the chain)'}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">None (top of the chain)</SelectItem>
                    {fatherOptions.map((m) => (
                      <SelectItem key={m.id} value={String(m.id)}>
                        ID{m.id} {m.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-1.5">
              <Label>Imports</Label>
              <CodeEditor
                value={form.imports}
                onChange={(v) => setForm({ ...form, imports: v })}
                language="python"
                height="90px"
                placeholder="import ..."
                ariaLabel="Imports"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Code *</Label>
              <CodeEditor
                value={form.code}
                onChange={(v) => setForm({ ...form, code: v })}
                language="python"
                height="360px"
                placeholder={placeholder}
                ariaLabel="Model code"
              />
            </div>

            <div className="flex justify-between border-t pt-4">
              <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
                Go Back
              </Button>
              {valid && (
                <Button type="submit" disabled={formInvalid}>
                  {create ? 'Create' : 'Edit'}
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
