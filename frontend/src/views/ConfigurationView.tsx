import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import MultiSelect from '@/components/MultiSelect'
import { getFatherModels, getConfiguration, createConfiguration, editConfiguration } from '@/api'
import { useNotify } from '@/notify'
import type { SimpleModel } from '@/types'

interface FormState {
  name: string
  description: string
  ml_models: number[]
}

export default function ConfigurationView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()

  const configurationId = id ? Number(id) : undefined
  const create = configurationId === undefined
  const [valid, setValid] = useState(true)
  const [form, setForm] = useState<FormState>({ name: '', description: '', ml_models: [] })
  // Only models at the top of a distributed chain (or plain models) are selectable.
  const [models, setModels] = useState<SimpleModel[]>([])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const list = await getFatherModels()
        if (!cancelled) setModels(list)
      } catch {
        if (!cancelled) notify.error('Error connecting with the server')
      }
      if (!create && configurationId !== undefined) {
        try {
          const configuration = await getConfiguration(configurationId)
          if (cancelled) return
          setForm({
            name: configuration.name,
            description: configuration.description,
            ml_models: (configuration.ml_models || []).map((m) => (typeof m === 'number' ? m : m.id)),
          })
        } catch {
          if (!cancelled) {
            setValid(false)
            notify.error('Error configuration not found')
          }
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configurationId])

  const formInvalid = !form.name || form.ml_models.length === 0

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      if (create) {
        await createConfiguration(form)
        notify.ok('Configuration created')
      } else if (configurationId !== undefined) {
        await editConfiguration(configurationId, form)
        notify.ok('Configuration updated')
      }
      navigate('/configurations')
    } catch (err) {
      notify.error(`Error ${create ? 'creating' : 'updating'} the configuration: ` + (err as Error).message)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>{create ? 'Create Configuration' : 'Edit Configuration'}</CardTitle>
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

            <div className="space-y-1.5">
              <Label>ML Models *</Label>
              <MultiSelect
                options={models.map((m) => ({ value: String(m.id), label: `ID${m.id} ${m.name}` }))}
                value={form.ml_models.map(String)}
                onChange={(v) => setForm({ ...form, ml_models: v.map(Number) })}
                placeholder="Select models"
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
