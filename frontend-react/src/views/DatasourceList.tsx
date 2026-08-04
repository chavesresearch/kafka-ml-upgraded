import { useEffect, useState } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import { LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import DataTable from '@/components/DataTable'
import { getDatasources, deployDatasource } from '@/api'
import { useNotify } from '@/notify'
import { truncate } from '@/logic/format'
import type { Datasource } from '@/types'

export default function DatasourceList() {
  const notify = useNotify()
  const [datasources, setDatasources] = useState<Datasource[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedDatasource, setSelectedDatasource] = useState<Datasource | null>(null)
  const [targetDeployment, setTargetDeployment] = useState<number | null>(null)

  useEffect(() => {
    getDatasources()
      .then(setDatasources)
      .catch(() => notify.error('Error connecting with the server'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function openSendDialog(datasource: Datasource) {
    setSelectedDatasource(datasource)
    setTargetDeployment(null)
    setDialogOpen(true)
  }

  async function send() {
    if (!selectedDatasource) return
    const data = { ...selectedDatasource, deployment: String(targetDeployment) }
    setDialogOpen(false)
    try {
      await deployDatasource(data)
      notify.ok('Datasource sent to Kafka. Refresh the page in a while to see it')
    } catch (err) {
      notify.error('Error sending the datasource: ' + (err as Error).message)
    }
  }

  const columns: ColumnDef<Datasource, unknown>[] = [
    { accessorKey: 'description', header: 'Description', enableSorting: false },
    { accessorKey: 'deployment', header: 'Deployment' },
    { accessorKey: 'input_format', header: 'Input format', enableSorting: false },
    {
      id: 'input_config',
      header: 'Input configuration',
      enableSorting: false,
      cell: ({ row }) => <span title={row.original.input_config}>{truncate(row.original.input_config, 10)}</span>,
    },
    { accessorKey: 'topic', header: 'Kafka topic', enableSorting: false },
    { accessorKey: 'validation_rate', header: 'Validation rate', enableSorting: false },
    { accessorKey: 'test_rate', header: 'Test rate', enableSorting: false },
    { accessorKey: 'total_msg', header: 'Total msg', enableSorting: false },
    { accessorKey: 'time', header: 'Time' },
    {
      id: 'send',
      header: 'Send again',
      enableSorting: false,
      cell: ({ row }) => (
        <Button variant="ghost" size="icon" title="Send again to another deployment" onClick={() => openSendDialog(row.original)}>
          <LogIn className="size-4" />
        </Button>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Datasources received</h1>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send datasource to deployment</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Please, make sure that the timestamp of the datasource is less than KAFKA_LOG_RETENTION_DAYS. Otherwise, the
            datasource could have been deleted from Kafka.
          </p>
          <div className="space-y-1.5">
            <Label>Deployment ID *</Label>
            <Input
              type="number"
              value={targetDeployment ?? ''}
              onChange={(e) => setTargetDeployment(e.target.value === '' ? null : Number(e.target.value))}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button disabled={targetDeployment == null} onClick={send}>
              Send
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DataTable columns={columns} data={datasources} />
    </div>
  )
}
