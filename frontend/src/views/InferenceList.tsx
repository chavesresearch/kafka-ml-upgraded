import { useCallback, useEffect, useState } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import { Check, Square, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import DataTable from '@/components/DataTable'
import { useConfirm } from '@/hooks/useConfirm'
import { getInferences, stopInference, deleteInference } from '@/api'
import { useNotify } from '@/notify'
import { truncate } from '@/logic/format'
import type { Inference } from '@/types'

export default function InferenceList() {
  const notify = useNotify()
  const { confirm, dialog } = useConfirm()
  const [inferences, setInferences] = useState<Inference[]>([])

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
    { accessorKey: 'model_result', header: 'Training ID' },
    { accessorKey: 'replicas', header: 'Replicas', enableSorting: false },
    { accessorKey: 'input_format', header: 'Input format', enableSorting: false },
    {
      id: 'input_config',
      header: 'Input configuration',
      enableSorting: false,
      cell: ({ row }) => <span title={row.original.input_config}>{truncate(row.original.input_config, 10)}</span>,
    },
    { accessorKey: 'external_host', header: 'Host', enableSorting: false },
    { accessorKey: 'input_topic', header: 'Kafka input topic', enableSorting: false },
    { accessorKey: 'output_topic', header: 'Kafka output topic', enableSorting: false },
    { accessorKey: 'output_upper', header: 'Kafka output to upper model', enableSorting: false },
    { accessorKey: 'limit', header: 'Prediction limit', enableSorting: false },
    { accessorKey: 'time', header: 'Time' },
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

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Inference</h1>
      <DataTable columns={columns} data={inferences} getRowId={(i) => String(i.id)} />
      {dialog}
    </div>
  )
}
