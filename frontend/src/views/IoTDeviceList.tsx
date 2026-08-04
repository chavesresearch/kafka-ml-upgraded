import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import { CloudUpload, CloudDownload, Copy, Pencil, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import DataTable from '@/components/DataTable'
import { useConfirm } from '@/hooks/useConfirm'
import { getIoTDevices, deleteIoTDevice } from '@/api'
import { useNotify } from '@/notify'
import type { IoTDevice } from '@/types'

export default function IoTDeviceList() {
  const notify = useNotify()
  const { confirm, dialog } = useConfirm()
  const [devices, setDevices] = useState<IoTDevice[]>([])

  useEffect(() => {
    getIoTDevices()
      .then(setDevices)
      .catch(() => notify.error('Error connecting with the server'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      notify.ok('Copied to clipboard')
    } catch (err) {
      notify.error('Error copying to clipboard: ' + err)
    }
  }

  function confirmDelete(id: number, token: string) {
    confirm({
      header: 'Are you sure?',
      message: `You will remove Device ${token}`,
      accept: async () => {
        try {
          await deleteIoTDevice(id)
          setDevices((prev) => prev.filter((d) => d.id !== id))
          notify.ok('Device deleted')
        } catch (err) {
          notify.error('Error deleting the device: ' + (err as Error).message)
        }
      },
    })
  }

  const columns: ColumnDef<IoTDevice, unknown>[] = [
    { accessorKey: 'token', header: 'MQTT ID' },
    { accessorKey: 'friendly_name', header: 'Friendly Name' },
    {
      id: 'broker',
      header: 'MQTT Broker',
      enableSorting: false,
      cell: ({ row }) => `${row.original.mqtt_address}:${row.original.mqtt_port}`,
    },
    {
      id: 'configuration',
      header: 'Configuration',
      enableSorting: false,
      cell: ({ row }) => (
        <Button variant="ghost" size="icon" title="Copy configuration" onClick={() => copyToClipboard(row.original.backlog)}>
          <Copy className="size-4" />
        </Button>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      enableSorting: false,
      cell: ({ row }) =>
        row.original.status === 'connected' ? (
          <CloudUpload className="size-4 text-emerald-500" aria-label="connected" />
        ) : (
          <CloudDownload className="size-4 text-muted-foreground" aria-label="disconnected" />
        ),
    },
    {
      id: 'actions',
      header: 'Actions',
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" title="View/edit device" asChild>
            <Link to={`/device/${row.original.id}`}>
              <Pencil className="size-4" />
            </Link>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            title="Delete device"
            onClick={() => confirmDelete(row.original.id, row.original.token)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Tasmota ML-Enabled IoT Devices</h1>
        <span className="flex-1" />
        <Button size="icon" className="rounded-full" title="Add a new device" asChild>
          <Link to="/devices-create">
            <Plus className="size-4" />
          </Link>
        </Button>
      </div>

      <DataTable columns={columns} data={devices} getRowId={(d) => String(d.id)} />
      {dialog}
    </div>
  )
}
