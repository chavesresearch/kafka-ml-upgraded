import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import { Check, Info, Square, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import DataTable from '@/components/DataTable'
import { useConfirm } from '@/hooks/useConfirm'
import { getInferences, stopInference, deleteInference } from '@/api'
import { useNotify } from '@/notify'
import { formatDate } from '@/logic/format'
import type { Inference } from '@/types'

export default function InferenceList() {
  const navigate = useNavigate()
  const notify = useNotify()
  const { confirm, dialog } = useConfirm()
  const [inferences, setInferences] = useState<Inference[]>([])
  const [infoDialogOpen, setInfoDialogOpen] = useState(false)
  const [infoDialogData, setInfoDialogData] = useState<Inference | null>(null)

  const refreshData = useCallback(async () => {
    try {
      setInferences(await getInferences())
    } catch {
      notify.error('Error connecting with the server')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    refreshData()
  }, [refreshData])

  function confirmStopping(id: number) {
    confirm({
      header: 'Are you sure?',
      message: `You will stop Inference ${id} running from Kubernetes`,
      accept: async () => {
        try {
          await stopInference(id)
          notify.ok('Inference stopped')
          refreshData()
        } catch (err) {
          notify.error('Error stopping the inference: ' + (err as Error).message)
        }
      },
    })
  }

  function openInfoDialog(inference: Inference) {
    setInfoDialogData(inference)
    setInfoDialogOpen(true)
  }

  function confirmDeletion(id: number) {
    confirm({
      header: 'Are you sure?',
      message: `You will remove Inference ${id}`,
      accept: async () => {
        try {
          await deleteInference(id)
          setInferences((prev) => prev.filter((i) => i.id !== id))
          notify.ok('Inference deleted')
        } catch (err) {
          notify.error('Error deleting the inference: ' + (err as Error).message)
        }
      },
    })
  }

  const columns: ColumnDef<Inference, unknown>[] = [
    { accessorKey: 'id', header: 'ID' },
    {
      accessorKey: 'model_result',
      header: 'Training ID',
      cell: ({ row }) => (
        <button
          type="button"
          className="text-primary hover:underline"
          title="View training result chart"
          onClick={() => navigate(`/results/chart/${row.original.model_result}`)}
        >
          {row.original.model_result}
        </button>
      ),
    },
    { accessorKey: 'replicas', header: 'Replicas', enableSorting: false },
    {
      id: 'info',
      header: 'Info',
      enableSorting: false,
      cell: ({ row }) => (
        <Button variant="ghost" size="icon" title="Connection details" onClick={() => openInfoDialog(row.original)}>
          <Info className="size-4" />
        </Button>
      ),
    },
    {
      accessorKey: 'time',
      header: 'Time',
      cell: ({ row }) => formatDate(row.original.time),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) =>
        row.original.status === 'stopped' ? (
          <Square className="size-4 text-amber-500" aria-label="stopped" />
        ) : row.original.status === 'deployed' ? (
          <Check className="size-4 text-emerald-500" aria-label="deployed" />
        ) : null,
    },
    {
      id: 'manage',
      header: 'Manage',
      enableSorting: false,
      cell: ({ row }) => {
        const inference = row.original
        if (inference.status === 'stopped') {
          return (
            <Button variant="ghost" size="icon" title="Remove inference" onClick={() => confirmDeletion(inference.id)}>
              <Trash2 className="size-4" />
            </Button>
          )
        }
        if (inference.status === 'deployed') {
          return (
            <Button variant="ghost" size="icon" title="Stop inference" onClick={() => confirmStopping(inference.id)}>
              <Square className="size-4" />
            </Button>
          )
        }
        return null
      },
    },
  ]

  const infoRows = infoDialogData
    ? [
        { name: 'Input format', value: infoDialogData.input_format },
        { name: 'Input configuration', value: infoDialogData.input_config },
        { name: 'Host', value: infoDialogData.external_host },
        { name: 'Kafka input topic', value: infoDialogData.input_topic },
        { name: 'Kafka output topic', value: infoDialogData.output_topic },
        { name: 'Kafka output to upper model', value: infoDialogData.output_upper },
        { name: 'Prediction limit', value: infoDialogData.limit },
      ]
    : []

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Inference</h1>
      <DataTable columns={columns} data={inferences} getRowId={(i) => String(i.id)} />

      <Dialog open={infoDialogOpen} onOpenChange={setInfoDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Connection details{infoDialogData && ` — Inference ${infoDialogData.id}`}</DialogTitle>
          </DialogHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Field</TableHead>
                <TableHead className="text-right">Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {infoRows.map((row) => (
                <TableRow key={row.name}>
                  <TableCell className="w-36 align-top font-medium whitespace-normal">{row.name}</TableCell>
                  <TableCell className="text-right align-top whitespace-normal break-all">
                    {row.value != null && row.value !== '' ? (
                      String(row.value)
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DialogContent>
      </Dialog>
      {dialog}
    </div>
  )
}
