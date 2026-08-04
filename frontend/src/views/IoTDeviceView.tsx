import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { getIoTDevice, createIoTDevice, editIoTDevice } from '@/api'
import { useNotify } from '@/notify'

interface FormState {
  friendly_name: string
  mqtt_address: string
  mqtt_port: number | string
  mqtt_username: string
  mqtt_password: string
}

const emptyForm: FormState = {
  friendly_name: '',
  mqtt_address: '',
  mqtt_port: '',
  mqtt_username: '',
  mqtt_password: '',
}

export default function IoTDeviceView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()

  const deviceId = id ? Number(id) : undefined
  const create = deviceId === undefined
  const [valid, setValid] = useState(true)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!create && deviceId !== undefined) {
        try {
          const device = await getIoTDevice(deviceId)
          if (cancelled) return
          setForm({
            friendly_name: device.friendly_name,
            mqtt_address: device.mqtt_address,
            mqtt_port: device.mqtt_port,
            mqtt_username: device.mqtt_username,
            mqtt_password: device.mqtt_password,
          })
        } catch {
          if (!cancelled) {
            setValid(false)
            notify.error('Error IoT Device not found')
          }
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceId])

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const formInvalid = !form.friendly_name

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      if (create) {
        await createIoTDevice(form)
        notify.ok('IoT Device created')
      } else if (deviceId !== undefined) {
        await editIoTDevice(deviceId, form)
        notify.ok('IoT Device updated')
      }
      navigate('/devices')
    } catch (err) {
      notify.error(`Error ${create ? 'creating' : 'updating'} the IoT Device: ` + (err as Error).message)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>{create ? 'Create IoT Device' : 'Edit IoT Device'}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
            <div className="space-y-1.5">
              <Label>Friendly Name *</Label>
              <Input autoFocus value={form.friendly_name} onChange={(e) => set('friendly_name', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>MQTT Address</Label>
              <Input value={form.mqtt_address} onChange={(e) => set('mqtt_address', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>MQTT Port</Label>
              <Input value={form.mqtt_port} onChange={(e) => set('mqtt_port', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>MQTT User</Label>
              <Input value={form.mqtt_username} onChange={(e) => set('mqtt_username', e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>MQTT Password</Label>
              <div className="flex gap-2">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={form.mqtt_password}
                  onChange={(e) => set('mqtt_password', e.target.value)}
                />
                <Button type="button" variant="outline" onClick={() => setShowPassword((v) => !v)}>
                  {showPassword ? 'Hide' : 'Show'}
                </Button>
              </div>
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
