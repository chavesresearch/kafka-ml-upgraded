import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, Play, ExternalLink, Trash2, Plus, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import TooltipIconButton from '@/components/TooltipIconButton'
import { useConfirm } from '@/hooks/useConfirm'
import { getConfigurations, deleteConfiguration } from '@/api'
import { useNotify } from '@/notify'
import { formatDate } from '@/logic/format'
import type { Configuration } from '@/types'

export default function ConfigurationList() {
  const notify = useNotify()
  const navigate = useNavigate()
  const { confirm, dialog } = useConfirm()
  const [configurations, setConfigurations] = useState<Configuration[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    getConfigurations()
      .then(setConfigurations)
      .catch(() => notify.error('Error connecting with the server'))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Same behavior as the old datafilter pipe: match any field, case-insensitive.
  const filtered = useMemo(() => {
    const text = filter.trim().toLowerCase()
    if (!text) return configurations
    return configurations.filter((c) => Object.values(c).some((v) => String(v).toLowerCase().includes(text)))
  }, [configurations, filter])

  function confirmDelete(id: number) {
    confirm({
      header: 'Are you sure?',
      message: `You will remove Configuration ${id}`,
      accept: async () => {
        try {
          await deleteConfiguration(id)
          setConfigurations((prev) => prev.filter((c) => c.id !== id))
          notify.ok('Configuration deleted')
        } catch (err) {
          notify.error('Error deleting the configuration: ' + (err as Error).message)
        }
      },
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Configurations</h1>
        <span className="flex-1" />
        <TooltipIconButton tooltip="Add a configuration" className="rounded-full" asChild>
          <Link to="/configuration-create">
            <Plus className="size-4" />
          </Link>
        </TooltipIconButton>
      </div>

      <Input placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="max-w-xs" />

      {filtered.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">{loading ? 'Loading…' : 'No configurations.'}</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((configuration) => (
          <Card key={configuration.id}>
            <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
              <div>
                <h3 className="font-semibold">{configuration.name}</h3>
                <p className="text-sm text-muted-foreground">{configuration.description}</p>
              </div>
              <div className="flex gap-1">
                <TooltipIconButton
                  variant="ghost"
                  tooltip="View"
                  onClick={() => navigate(`/configuration/${configuration.id}`)}
                >
                  <Eye className="size-4" />
                </TooltipIconButton>
                <TooltipIconButton variant="ghost" tooltip="Deploy" onClick={() => navigate(`/deploy/${configuration.id}`)}>
                  <Play className="size-4" />
                </TooltipIconButton>
                <TooltipIconButton
                  variant="ghost"
                  tooltip="Import trained model"
                  onClick={() => navigate(`/import/${configuration.id}`)}
                >
                  <Upload className="size-4" />
                </TooltipIconButton>
                <TooltipIconButton
                  variant="ghost"
                  tooltip="Deployments"
                  onClick={() => navigate(`/deployments/${configuration.id}`)}
                >
                  <ExternalLink className="size-4" />
                </TooltipIconButton>
                <TooltipIconButton variant="ghost" tooltip="Remove" onClick={() => confirmDelete(configuration.id)}>
                  <Trash2 className="size-4" />
                </TooltipIconButton>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <h4 className="mb-1.5 text-sm font-semibold">ML Models:</h4>
                <div className="flex flex-wrap gap-1.5">
                  {configuration.ml_models.map((model) => (
                    <Button key={model.id} variant="outline" size="sm" title={`View/Edit Model ${model.id}`} asChild>
                      <Link to={`/model/${model.id}`}>{model.name}</Link>
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <h4 className="mb-1.5 text-sm font-semibold">Deployments:</h4>
                <div className="flex flex-wrap gap-1.5">
                  {(configuration.deployments ?? []).map((deployment) => (
                    <Button
                      key={deployment.id}
                      variant="secondary"
                      size="sm"
                      title={`View Deployment ${formatDate(deployment.time)}`}
                      asChild
                    >
                      <Link to={`/results/${deployment.id}`}>{formatDate(deployment.time)}</Link>
                    </Button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      {dialog}
    </div>
  )
}
