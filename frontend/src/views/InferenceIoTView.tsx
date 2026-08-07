import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import MultiSelect from '@/components/MultiSelect'
import CodeEditor from '@/components/CodeEditor'
import { getIoTDevices, getResults, deployIoTInference } from '@/api'
import { useNotify } from '@/notify'
import type { IoTDevice } from '@/types'

export default function InferenceIoTView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()

  const resultID = Number(id)
  const [availableDevices, setAvailableDevices] = useState<IoTDevice[]>([])
  const [deviceToken, setDeviceToken] = useState<string[]>([])
  const [code, setCode] = useState('')
  const [applyIntQuant, setApplyIntQuant] = useState(false)
  // undefined while loading, null if the result can't be deployed to IoT
  // (not found, or a non-TensorFlow model - mlcode_executor/pthexecutor
  // has no TFLite-export equivalent, see backend/app/controllers/
  // iot_devices.py's own framework check), true once confirmed usable.
  const [ready, setReady] = useState<boolean | undefined>(undefined)

  useEffect(() => {
    getIoTDevices()
      .then((devices) => setAvailableDevices(devices.filter((d) => d.status === 'connected')))
      .catch(() => notify.error('Error fetching devices'))
    getResults()
      .then((results) => {
        const result = results.find((r) => r.id === resultID)
        setReady(result != null && result.model.framework === 'tf')
      })
      .catch(() => setReady(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const formInvalid = deviceToken.length === 0 || !code

  if (ready === false) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            IoT/TFLite deployment is only supported for TensorFlow training
            results. This result either doesn't exist or wasn't trained
            with TensorFlow.
            <div className="mt-4">
              <Button variant="ghost" onClick={() => navigate('/results')}>
                Back to results
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    // Backend contract (iot_devices.py): keys are 'code', 'device_token', 'model_result', 'applyIntQuant'.
    const payload = { device_token: deviceToken, code, applyIntQuant, model_result: resultID }
    try {
      await deployIoTInference(resultID, payload)
      notify.ok('Model deployed for inference')
      navigate('/results')
    } catch {
      notify.error('Error deploying the model for inference')
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Deploy Training result {resultID} for inference in Tasmota</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
            <div className="space-y-1.5">
              <Label>Available Tasmotas for deploy *</Label>
              <MultiSelect
                options={availableDevices.map((d) => ({ value: d.token, label: `${d.friendly_name} | ${d.token}` }))}
                value={deviceToken}
                onChange={setDeviceToken}
                placeholder="Select devices"
              />
            </div>

            <div className="space-y-1.5">
              <Label>Berry Script for Tasmota *</Label>
              <CodeEditor value={code} onChange={setCode} language="berry" height="320px" ariaLabel="Berry script for Tasmota" />
            </div>

            <label className="flex items-center gap-2 text-sm font-normal">
              <Checkbox checked={applyIntQuant} onCheckedChange={(v) => setApplyIntQuant(v === true)} />
              Apply int8 quantization
            </label>

            <div className="flex justify-between border-t pt-4">
              <Button type="button" variant="ghost" onClick={() => navigate(-1)}>
                Go Back
              </Button>
              <Button type="submit" disabled={formInvalid}>
                Deploy
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
