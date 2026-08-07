import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Eye, MoreVertical, Trash2, PencilLine, LogIn, Square, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useConfirm } from '@/hooks/useConfirm'
import { getDeployments, getDeploymentsOfConfiguration, getConfiguration, deleteDeployment } from '@/api'
import { useNotify } from '@/notify'
import { formatDate } from '@/logic/format'
import type { Configuration, DeploymentInfo, TrainingStatus } from '@/types'
import { cn } from '@/lib/utils'

const statusClass: Record<TrainingStatus, string> = {
  created: 'bg-secondary text-secondary-foreground',
  deployed: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
  stopped: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  finished: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
}

// Same icon-per-status mapping ResultList.tsx uses - status here was
// previously conveyed by chip color alone, not colorblind-friendly and
// inconsistent with how the Training/Results table shows the same status.
const statusIcons: Record<TrainingStatus, typeof PencilLine> = {
  created: PencilLine,
  deployed: LogIn,
  stopped: Square,
  finished: Check,
}

export default function DeploymentList() {
  const { id } = useParams()
  const navigate = useNavigate()
  const notify = useNotify()
  const { confirm, dialog } = useConfirm()

  const configurationID = id ? Number(id) : undefined
  const [configuration, setConfiguration] = useState<Configuration | null>(null)
  const [deployments, setDeployments] = useState<DeploymentInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    async function load() {
      try {
        if (configurationID !== undefined) {
          setConfiguration(await getConfiguration(configurationID))
          setDeployments(await getDeploymentsOfConfiguration(configurationID))
        } else {
          setDeployments(await getDeployments())
        }
      } catch {
        notify.error('Error connecting with the server')
      } finally {
        setLoading(false)
      }
    }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configurationID])

  const filtered = useMemo(() => {
    const text = filter.trim().toLowerCase()
    if (!text) return deployments
    return deployments.filter((d) => Object.values(d).some((v) => String(v).toLowerCase().includes(text)))
  }, [deployments, filter])

  function confirmDelete(id: number) {
    confirm({
      header: 'Are you sure?',
      message: `You will remove Deployment ${id}`,
      accept: async () => {
        try {
          await deleteDeployment(id)
          setDeployments((prev) => prev.filter((d) => d.id !== id))
          notify.ok('Deployment deleted')
        } catch (err) {
          notify.error('Error deleting the deployment: ' + (err as Error).message)
        }
      },
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">
          Deployments
          {configuration && <span className="ml-2 text-base font-normal text-muted-foreground">of Configuration {configuration.name}</span>}
        </h1>
      </div>

      <Input placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="max-w-xs" />

      {filtered.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">{loading ? 'Loading…' : 'No deployments.'}</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((deployment) => (
          <Card key={deployment.id}>
            <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
              <div>
                <h3 className="font-semibold">Deployment {deployment.id}</h3>
                <p className="text-sm text-muted-foreground">{formatDate(deployment.time)}</p>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <MoreVertical className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => navigate(`/results/${deployment.id}`)}>
                    <Eye /> Results
                  </DropdownMenuItem>
                  <DropdownMenuItem variant="destructive" onClick={() => confirmDelete(deployment.id)}>
                    <Trash2 /> Remove
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <h4 className="mb-1.5 font-semibold">Training results</h4>
                <div className="flex flex-col items-start gap-1.5">
                  {deployment.results.map((result) => {
                    const StatusIcon = statusIcons[result.status]
                    return (
                      <Button
                        key={result.id}
                        size="sm"
                        className={cn('h-auto max-w-full gap-1.5 py-1 whitespace-normal', statusClass[result.status])}
                        variant="secondary"
                        title={`Result ${result.id} - status: ${result.status}, last change: ${formatDate(result.status_changed)}`}
                        asChild
                      >
                        <Link to={`/results/${deployment.id}`}>
                          <StatusIcon className="size-3.5 shrink-0" />
                          Model {result.model.name}
                        </Link>
                      </Button>
                    )
                  })}
                </div>
              </div>
              <div>
                <h4 className="mb-1.5 font-semibold">Configuration:</h4>
                <Button variant="outline" size="sm" asChild>
                  <Link to={`/configuration/${deployment.configuration.id}`}>{deployment.configuration.name}</Link>
                </Button>
              </div>
              <div>
                <h4 className="font-semibold">Batch size:</h4>
                <p>{deployment.batch}</p>
              </div>
              {deployment.tf_kwargs_fit && (
                <div>
                  <h4 className="font-semibold">TF Training arguments:</h4>
                  <p>{deployment.tf_kwargs_fit}</p>
                </div>
              )}
              {deployment.tf_kwargs_val && (
                <div>
                  <h4 className="font-semibold">TF Validation arguments:</h4>
                  <p>{deployment.tf_kwargs_val}</p>
                </div>
              )}
              {deployment.pth_kwargs_fit && (
                <div>
                  <h4 className="font-semibold">PTH Training arguments:</h4>
                  <p>{deployment.pth_kwargs_fit}</p>
                </div>
              )}
              {deployment.pth_kwargs_val && (
                <div>
                  <h4 className="font-semibold">PTH Validation arguments:</h4>
                  <p>{deployment.pth_kwargs_val}</p>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
      {dialog}
    </div>
  )
}
