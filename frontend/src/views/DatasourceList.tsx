import { useEffect, useState } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import { Info, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import DataTable from '@/components/DataTable'
import TooltipIconButton from '@/components/TooltipIconButton'
import { getDatasources, deployDatasource } from '@/api'
import { useNotify } from '@/notify'
import { formatDate, prettyJson } from '@/logic/format'
import type { Datasource } from '@/types'

export default function DatasourceList() {
  const notify = useNotify()
  const [datasources, setDatasources] = useState<Datasource[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedDatasource, setSelectedDatasource] = useState<Datasource | null>(null)
  const [targetDeployment, setTargetDeployment] = useState<number | null>(null)
  const [propertiesDialogData, setPropertiesDialogData] = useState<Datasource | null>(null)

  useEffect(() => {
    getDatasources()
      .then(setDatasources)
      .catch(() => notify.error('Error connecting with the server'))
      .finally(() => setLoading(false))
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
    { accessorKey: 'topic', header: 'Kafka topic', enableSorting: false },
    {
      accessorKey: 'time',
      header: 'Time',
      cell: ({ row }) => formatDate(row.original.time),
    },
    {
      id: 'properties',
      header: 'Properties',
      enableSorting: false,
      cell: ({ row }) => (
        <TooltipIconButton
          variant="ghost"
          tooltip="Datasource properties"
          onClick={() => setPropertiesDialogData(row.original)}
        >
          <Info className="size-4" />
        </TooltipIconButton>
      ),
    },
    {
      id: 'send',
      header: 'Send again',
      enableSorting: false,
      cell: ({ row }) => (
        <TooltipIconButton variant="ghost" tooltip="Send again to another deployment" onClick={() => openSendDialog(row.original)}>
          <LogIn className="size-4" />
        </TooltipIconButton>
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

      <Dialog open={propertiesDialogData != null} onOpenChange={(open) => !open && setPropertiesDialogData(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Datasource properties</DialogTitle>
          </DialogHeader>
          {propertiesDialogData && (
            <Table>
              <TableBody>
                <TableRow>
                  <TableCell className="font-medium">Input format</TableCell>
                  <TableCell>{propertiesDialogData.input_format}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="align-top font-medium">Input configuration</TableCell>
                  <TableCell>
                    <pre className="whitespace-pre-wrap break-all font-mono text-xs">
                      {prettyJson(propertiesDialogData.input_config)}
                    </pre>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Validation rate</TableCell>
                  <TableCell>{propertiesDialogData.validation_rate}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Test rate</TableCell>
                  <TableCell>{propertiesDialogData.test_rate}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="font-medium">Total msg</TableCell>
                  <TableCell>{propertiesDialogData.total_msg}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          )}
        </DialogContent>
      </Dialog>

      <DataTable columns={columns} data={datasources} loading={loading} />
    </div>
  )
}
