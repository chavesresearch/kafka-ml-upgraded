import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import {
  Info,
  LineChart,
  MoreVertical,
  Play,
  Wifi,
  Download,
  Trash2,
  Square,
  RefreshCw,
  PencilLine,
  LogIn,
  Check,
  GitCompareArrows,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import DataTable from '@/components/DataTable'
import TooltipIconButton from '@/components/TooltipIconButton'
import MetricsTable from '@/components/MetricsTable'
import MultiSelect from '@/components/MultiSelect'
import { useConfirm } from '@/hooks/useConfirm'
import { getResults, getResultsOfDeployment, deleteResult, stopTraining, getTrainedModel, downloadBlob } from '@/api'
import { useNotify } from '@/notify'
import { buildMetricsTable, formatDate } from '@/logic/format'
import { MAX_COMPARE_RESULTS } from '@/logic/plot'
import type { TrainingResult, TrainingStatus } from '@/types'

const statusIcons: Record<TrainingStatus, typeof PencilLine> = {
  created: PencilLine,
  deployed: LogIn,
  stopped: Square,
  finished: Check,
}

const statusColor: Record<TrainingStatus, string> = {
  created: 'text-muted-foreground',
  deployed: 'text-blue-500',
  stopped: 'text-amber-500',
  finished: 'text-emerald-500',
}

export default function ResultList() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()
  const { confirm, dialog } = useConfirm()

  const deploymentID = id ? Number(id) : undefined
  const [results, setResults] = useState<TrainingResult[]>([])
  const [loading, setLoading] = useState(true)
  const [metricsDialogOpen, setMetricsDialogOpen] = useState(false)
  const [metricsDialogData, setMetricsDialogData] = useState<TrainingResult | null>(null)
  const [compareIds, setCompareIds] = useState<string[]>([])

  const refreshData = useCallback(async () => {
    try {
      setResults(deploymentID !== undefined ? await getResultsOfDeployment(deploymentID) : await getResults())
    } catch {
      notify.error('Error connecting with the server')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deploymentID])

  useEffect(() => {
    refreshData()
  }, [refreshData])

  function openMetricsDialog(result: TrainingResult) {
    setMetricsDialogData(result)
    setMetricsDialogOpen(true)
  }

  async function downloadTrainedModel(id: number) {
    try {
      const { blob, headers } = await getTrainedModel(id)
      const framework = headers.get('ML-Framework')
      const extension = framework === 'pth' ? '.pth' : '.h5'
      downloadBlob(blob, `model-result${id}${extension}`)
    } catch {
      notify.error('Error downloading the model')
    }
  }

  function confirmDeletion(id: number) {
    confirm({
      header: 'Are you sure?',
      message: `You will remove Result ${id}`,
      accept: async () => {
        try {
          await deleteResult(id)
          setResults((prev) => prev.filter((r) => r.id !== id))
          notify.ok('Result deleted')
        } catch (err) {
          notify.error('Error deleting the result: ' + (err as Error).message)
        }
      },
    })
  }

  function confirmStopping(id: number) {
    confirm({
      header: 'Are you sure?',
      message: `You will stop Training result ${id} running from Kubernetes`,
      accept: async () => {
        try {
          await stopTraining(id)
          notify.ok('Training stopped')
          refreshData()
        } catch (err) {
          notify.error('Error stopping the training: ' + (err as Error).message)
        }
      },
    })
  }

  function onCompareSelectionChange(next: string[]) {
    if (next.length > MAX_COMPARE_RESULTS) {
      notify.error(`You can compare up to ${MAX_COMPARE_RESULTS} results at once`)
      return
    }
    setCompareIds(next)
  }

  function goToCompare() {
    navigate(`/results/compare?ids=${compareIds.join(',')}`)
  }

  const columns: ColumnDef<TrainingResult, unknown>[] = [
    { accessorKey: 'id', header: 'ID' },
    {
      id: 'model',
      header: 'Model',
      accessorFn: (r) => r.model.name,
    },
    {
      id: 'metricsInfo',
      header: 'Metrics',
      enableSorting: false,
      cell: ({ row }) => (
        <TooltipIconButton variant="ghost" tooltip="Metrics" onClick={() => openMetricsDialog(row.original)}>
          <Info className="size-4" />
        </TooltipIconButton>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const Icon = statusIcons[row.original.status]
        return <Icon className={`size-4 ${statusColor[row.original.status]}`} aria-label={row.original.status} />
      },
    },
    {
      accessorKey: 'status_changed',
      header: 'Last status change',
      cell: ({ row }) => formatDate(row.original.status_changed),
    },
    {
      id: 'inference',
      header: 'Inference',
      enableSorting: false,
      cell: ({ row }) =>
        row.original.status === 'finished' ? (
          <TooltipIconButton
            variant="ghost"
            tooltip="Deploy inference"
            onClick={() => navigate(`/results/inference/${row.original.id}`)}
          >
            <Play className="size-4" />
          </TooltipIconButton>
        ) : null,
    },
    {
      id: 'actions',
      header: 'Actions',
      enableSorting: false,
      cell: ({ row }) => {
        const result = row.original
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreVertical className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {result.status === 'finished' && (
                <>
                  {result.model.framework === 'tf' && (
                    <DropdownMenuItem onClick={() => navigate(`/results/inference-iot/${result.id}`)}>
                      <Wifi /> Deploy on IoT
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem onClick={() => downloadTrainedModel(result.id)}>
                    <Download /> Download
                  </DropdownMenuItem>
                </>
              )}
              {result.status !== 'deployed' ? (
                <DropdownMenuItem variant="destructive" onClick={() => confirmDeletion(result.id)}>
                  <Trash2 /> Remove
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem variant="destructive" onClick={() => confirmStopping(result.id)}>
                  <Square /> Stop
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )
      },
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">
          Training results
          {deploymentID !== undefined && (
            <span className="ml-2 text-base font-normal text-muted-foreground">of Deployment {deploymentID}</span>
          )}
        </h1>
        <span className="flex-1" />
        <TooltipIconButton variant="ghost" tooltip="Refresh" onClick={refreshData}>
          <RefreshCw className="size-4" />
        </TooltipIconButton>
      </div>

      {results.length >= 2 && (
        <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4">
          <div className="min-w-64 flex-1 space-y-1.5">
            <Label>Compare results</Label>
            <MultiSelect
              options={results.map((r) => ({ value: String(r.id), label: `Result ${r.id} — ${r.model.name}` }))}
              value={compareIds}
              onChange={onCompareSelectionChange}
              placeholder="Select 2 or more results"
            />
          </div>
          <Button variant="outline" disabled={compareIds.length < 2} onClick={goToCompare}>
            <GitCompareArrows /> Compare ({compareIds.length})
          </Button>
        </div>
      )}

      <DataTable columns={columns} data={results} getRowId={(r) => String(r.id)} loading={loading} />

      <Dialog open={metricsDialogOpen} onOpenChange={setMetricsDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Metrics{metricsDialogData && ` — Result ${metricsDialogData.id}`}</DialogTitle>
          </DialogHeader>
          {metricsDialogData &&
            (() => {
              const rows = buildMetricsTable(
                metricsDialogData.train_metrics,
                metricsDialogData.val_metrics,
                metricsDialogData.test_metrics
              )
              return (
                <div className="space-y-3">
                  <MetricsTable rows={rows} />
                  {metricsDialogData.training_time != null && (
                    <p className="text-sm text-muted-foreground">
                      Training time: {metricsDialogData.training_time}
                      {typeof metricsDialogData.training_time === 'number' ? 's' : ''}
                    </p>
                  )}
                </div>
              )
            })()}
          {metricsDialogData && (
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => navigate(`/results/chart/${metricsDialogData.id}`)}
              >
                <LineChart /> View full chart
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
      {dialog}
    </div>
  )
}
