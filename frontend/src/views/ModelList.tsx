import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, Pencil, Trash2, Plus, GitBranch } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import TooltipIconButton from '@/components/TooltipIconButton'
import FrameworkIcon from '@/components/FrameworkIcon'
import { useConfirm } from '@/hooks/useConfirm'
import { getModels, deleteModel } from '@/api'
import { useNotify } from '@/notify'
import { formatDate } from '@/logic/format'
import type { MLModel } from '@/types'

export default function ModelList() {
  const notify = useNotify()
  const navigate = useNavigate()
  const { confirm, dialog } = useConfirm()
  const [models, setModels] = useState<MLModel[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [viewing, setViewing] = useState<MLModel | null>(null)

  useEffect(() => {
    getModels()
      .then(setModels)
      .catch(() => notify.error('Error connecting with the server'))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Distributed models form a strict father -> child chain on the backend
  // (father_id is unique, a model has at most one child) rather than a
  // branching tree - walk each chain from its root once and render the
  // whole chain inside one card, in order of descendance.
  const chains = useMemo(() => {
    const childOf = new Map<number, MLModel>()
    for (const m of models) {
      if (m.father) childOf.set(m.father.id, m)
    }
    const roots = models.filter((m) => !m.father)
    return roots.map((root) => {
      const chain = [root]
      let current = root
      while (childOf.has(current.id)) {
        current = childOf.get(current.id)!
        chain.push(current)
      }
      return chain
    })
  }, [models])

  // Same behavior as the other list views: match any field across the
  // whole chain, case-insensitive.
  const filtered = useMemo(() => {
    const text = filter.trim().toLowerCase()
    if (!text) return chains
    return chains.filter((chain) =>
      chain.some((m) => Object.values(m).some((v) => String(v).toLowerCase().includes(text))),
    )
  }, [chains, filter])

  function confirmDelete(id: number) {
    confirm({
      header: 'Are you sure?',
      message: `You will remove Model ${id}`,
      accept: async () => {
        try {
          await deleteModel(id)
          setModels((prev) => prev.filter((m) => m.id !== id))
          notify.ok('Model deleted')
        } catch (err) {
          notify.error('Error deleting the model: ' + (err as Error).message)
        }
      },
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Models</h1>
        <span className="flex-1" />
        <TooltipIconButton tooltip="Add a model" className="rounded-full" asChild>
          <Link to="/model-create">
            <Plus className="size-4" />
          </Link>
        </TooltipIconButton>
      </div>

      <Input placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="max-w-xs" />

      {filtered.length === 0 && (
        <p className="py-8 text-center text-muted-foreground">{loading ? 'Loading…' : 'No models.'}</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((chain) => {
          const root = chain[0]
          return (
            <Card key={root.id}>
              <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
                <div className="flex min-w-0 items-center gap-2">
                  <FrameworkIcon framework={root.framework} className="size-5 shrink-0" />
                  <div className="min-w-0">
                    <h3 className="truncate font-semibold">{root.name}</h3>
                    <p className="text-sm text-muted-foreground">{formatDate(root.updated_at || root.created_at)}</p>
                  </div>
                </div>
                <div className="flex shrink-0 gap-1">
                  <TooltipIconButton variant="ghost" tooltip="View model" onClick={() => setViewing(root)}>
                    <Eye className="size-4" />
                  </TooltipIconButton>
                  <TooltipIconButton variant="ghost" tooltip="Edit model" onClick={() => navigate(`/model/${root.id}`)}>
                    <Pencil className="size-4" />
                  </TooltipIconButton>
                  <TooltipIconButton variant="ghost" tooltip="Delete model" onClick={() => confirmDelete(root.id)}>
                    <Trash2 className="size-4" />
                  </TooltipIconButton>
                </div>
              </CardHeader>
              {chain.length > 1 && (
                <CardContent className="space-y-1.5">
                  {chain.slice(1).map((child, i) => (
                    <div
                      key={child.id}
                      className="flex items-center justify-between gap-2 rounded-md border py-1 pr-1 pl-2"
                      style={{ marginLeft: `${(i + 1) * 0.75}rem` }}
                    >
                      <div className="flex min-w-0 items-center gap-1.5">
                        <GitBranch className="size-3.5 shrink-0 text-muted-foreground" />
                        <FrameworkIcon framework={child.framework} className="size-3.5 shrink-0" />
                        <span className="truncate text-sm">{child.name}</span>
                      </div>
                      <div className="flex shrink-0 gap-0.5">
                        <TooltipIconButton
                          variant="ghost"
                          size="icon-sm"
                          tooltip="View model"
                          onClick={() => setViewing(child)}
                        >
                          <Eye className="size-3.5" />
                        </TooltipIconButton>
                        <TooltipIconButton
                          variant="ghost"
                          size="icon-sm"
                          tooltip="Edit model"
                          onClick={() => navigate(`/model/${child.id}`)}
                        >
                          <Pencil className="size-3.5" />
                        </TooltipIconButton>
                        <TooltipIconButton
                          variant="ghost"
                          size="icon-sm"
                          tooltip="Delete model"
                          onClick={() => confirmDelete(child.id)}
                        >
                          <Trash2 className="size-3.5" />
                        </TooltipIconButton>
                      </div>
                    </div>
                  ))}
                </CardContent>
              )}
            </Card>
          )
        })}
      </div>

      <Dialog open={viewing !== null} onOpenChange={(open) => !open && setViewing(null)}>
        <DialogContent className="max-w-lg sm:max-w-2xl">
          {viewing && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <FrameworkIcon framework={viewing.framework} />
                  {viewing.name}
                </DialogTitle>
                <DialogDescription>{viewing.description || 'No description.'}</DialogDescription>
              </DialogHeader>
              <div className="max-h-[60vh] space-y-3 overflow-y-auto">
                <div>
                  <h4 className="mb-1 text-sm font-semibold">Imports</h4>
                  <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs whitespace-pre-wrap">
                    {viewing.imports || '(none)'}
                  </pre>
                </div>
                <div>
                  <h4 className="mb-1 text-sm font-semibold">Code</h4>
                  <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs whitespace-pre-wrap">{viewing.code}</pre>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {dialog}
    </div>
  )
}
