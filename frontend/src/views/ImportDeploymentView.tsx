import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { getConfiguration, getDistributedConfiguration, importDeployment, type ImportDeploymentMetrics } from '@/api'
import { useNotify } from '@/notify'
import type { Configuration } from '@/types'

export default function ImportDeploymentView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()

  const configurationID = Number(id)
  const [configuration, setConfiguration] = useState<Configuration | null>(null)
  const [distributed, setDistributed] = useState(false)
  const [ready, setReady] = useState(false)

  const [file, setFile] = useState<File | null>(null)
  const [trainMetrics, setTrainMetrics] = useState('')
  const [valMetrics, setValMetrics] = useState('')
  const [testMetrics, setTestMetrics] = useState('')
  const [trainingTime, setTrainingTime] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const config = await getConfiguration(configurationID)
        if (cancelled) return
        setConfiguration(config)
        const dist = await getDistributedConfiguration(configurationID)
        if (!cancelled) setDistributed(Boolean(dist))
      } catch {
        if (!cancelled) notify.error('Configuration not found')
      } finally {
        if (!cancelled) setReady(true)
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configurationID])

  const singleModel = configuration && configuration.ml_models.length === 1 && !distributed ? configuration.ml_models[0] : null
  const unsupported = ready && configuration !== null && singleModel === null
  const extension = singleModel?.framework === 'pth' ? '.pth' : '.h5'

  function parseOptionalJson(label: string, value: string): Record<string, number[]> | undefined {
    if (value.trim() === '') return undefined
    try {
      return JSON.parse(value)
    } catch {
      throw new Error(`${label} is not valid JSON`)
    }
  }

  async function submit() {
    if (!singleModel || !file) return
    setSubmitting(true)
    try {
      const metrics: ImportDeploymentMetrics = {}
      try {
        metrics.train_metrics = parseOptionalJson('Train metrics', trainMetrics)
        metrics.val_metrics = parseOptionalJson('Validation metrics', valMetrics)
        metrics.test_metrics = parseOptionalJson('Test metrics', testMetrics)
      } catch (err) {
        notify.error((err as Error).message)
        setSubmitting(false)
        return
      }
      if (trainingTime !== '') metrics.training_time = Number(trainingTime)

      await importDeployment(configurationID, file, metrics)
      notify.ok('Model imported - ready for inference')
      navigate(`/deployments/${configurationID}`)
    } catch (err) {
      notify.error('Error importing the model: ' + (err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-xl font-semibold">Import a Trained Model</h1>

      {!ready ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : unsupported ? (
        <Card>
          <CardContent className="pt-6 text-muted-foreground">
            {distributed
              ? 'Importing a trained model is not supported for distributed configurations - it would need two coordinated weight files.'
              : 'Importing a trained model requires a configuration with exactly one model.'}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>
              {singleModel!.name} <span className="font-normal text-muted-foreground">({singleModel!.framework})</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Upload an already-trained {extension} file for this model. It's validated by actually
              loading it{singleModel!.framework === 'pth' ? " against this model's own code" : ''} before
              being accepted - a mismatched or corrupt file is rejected with the real error, nothing is
              created until it passes.
            </p>

            <div className="space-y-1.5">
              <Label htmlFor="trained-model-file">Trained model file ({extension})</Label>
              <Input
                id="trained-model-file"
                type="file"
                accept={extension}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="train-metrics">
                Train metrics (optional JSON, e.g. {'{"accuracy": [0.9], "loss": [0.2]}'})
              </Label>
              <Input
                id="train-metrics"
                value={trainMetrics}
                onChange={(e) => setTrainMetrics(e.target.value)}
                placeholder="{}"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="val-metrics">Validation metrics (optional JSON)</Label>
              <Input id="val-metrics" value={valMetrics} onChange={(e) => setValMetrics(e.target.value)} placeholder="{}" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="test-metrics">Test metrics (optional JSON)</Label>
              <Input id="test-metrics" value={testMetrics} onChange={(e) => setTestMetrics(e.target.value)} placeholder="{}" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="training-time">Training time in seconds (optional)</Label>
              <Input
                id="training-time"
                type="number"
                value={trainingTime}
                onChange={(e) => setTrainingTime(e.target.value)}
              />
            </div>

            <Button disabled={!file || submitting} onClick={submit}>
              {submitting ? 'Validating and importing…' : 'Import'}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
