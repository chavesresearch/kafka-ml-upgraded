import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import MultiSelect from '@/components/MultiSelect'
import CodeEditor from '@/components/CodeEditor'
import { getIoTDevices, deployIoTInference } from '@/api'
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

  useEffect(() => {
    getIoTDevices()
      .then((devices) => setAvailableDevices(devices.filter((d) => d.status === 'connected')))
      .catch(() => notify.error('Error fetching devices'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const formInvalid = deviceToken.length === 0 || !code

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
              <CodeEditor value={code} onChange={setCode} language="lua" height="320px" ariaLabel="Berry script for Tasmota" />
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
