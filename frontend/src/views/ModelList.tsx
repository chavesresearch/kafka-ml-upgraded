import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, Pencil, Trash2, Plus, GitBranch, GripVertical } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Card, CardAction, CardContent, CardHeader } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import TooltipIconButton from '@/components/TooltipIconButton'
import FrameworkIcon from '@/components/FrameworkIcon'
import { useConfirm } from '@/hooks/useConfirm'
import { getModels, deleteModel } from '@/api'
import { useNotify } from '@/notify'
import { formatDate } from '@/logic/format'
import { cn } from '@/lib/utils'
import type { MLModel } from '@/types'

interface ModelCardProps {
  chain: MLModel[]
  onView: (model: MLModel) => void
  onEdit: (id: number) => void
  onDelete: (id: number) => void
}

// CardHeader is a CSS grid (see components/ui/card.tsx) that only puts its
// action row in a second column, right-aligned, when it has a direct
// `CardAction` child (`has-data-[slot=card-action]:grid-cols-[1fr_auto]`) -
// a plain `<div>` of buttons instead just falls into the next implicit grid
// row below the title, which is why the icons rendered under the name
// instead of beside it.
function ModelCard({ chain, onView, onEdit, onDelete }: ModelCardProps) {
  const root = chain[0]
  return (
    <Card>
      <CardHeader>
        <div className="flex min-w-0 items-center gap-2">
          <FrameworkIcon framework={root.framework} className="size-5 shrink-0" />
          <div className="min-w-0">
            <h3 className="truncate font-semibold">{root.name}</h3>
            <p className="text-sm text-muted-foreground">{formatDate(root.updated_at || root.created_at)}</p>
          </div>
        </div>
        <CardAction className="flex gap-1">
          <TooltipIconButton variant="ghost" tooltip="View model" onClick={() => onView(root)}>
            <Eye className="size-4" />
          </TooltipIconButton>
          <TooltipIconButton variant="ghost" tooltip="Edit model" onClick={() => onEdit(root.id)}>
            <Pencil className="size-4" />
          </TooltipIconButton>
          <TooltipIconButton variant="ghost" tooltip="Delete model" onClick={() => onDelete(root.id)}>
            <Trash2 className="size-4" />
          </TooltipIconButton>
        </CardAction>
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
                <TooltipIconButton variant="ghost" size="icon-sm" tooltip="View model" onClick={() => onView(child)}>
                  <Eye className="size-3.5" />
                </TooltipIconButton>
                <TooltipIconButton
                  variant="ghost"
                  size="icon-sm"
                  tooltip="Edit model"
                  onClick={() => onEdit(child.id)}
                >
                  <Pencil className="size-3.5" />
                </TooltipIconButton>
                <TooltipIconButton
                  variant="ghost"
                  size="icon-sm"
                  tooltip="Delete model"
                  onClick={() => onDelete(child.id)}
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
}

type SectionKind = 'single' | 'distributed'

const SECTION_LABEL: Record<SectionKind, string> = {
  single: 'Single models',
  distributed: 'Distributed models',
}

export default function ModelList() {
  const notify = useNotify()
  const navigate = useNavigate()
  const { confirm, dialog } = useConfirm()
  const [models, setModels] = useState<MLModel[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [viewing, setViewing] = useState<MLModel | null>(null)
  // Single models above distributed by default - user-reorderable from
  // there by dragging a row's handle, not persisted across reloads.
  const [sectionOrder, setSectionOrder] = useState<SectionKind[]>(['single', 'distributed'])
  const [draggedKind, setDraggedKind] = useState<SectionKind | null>(null)
  const [dragOverKind, setDragOverKind] = useState<SectionKind | null>(null)

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

  // Split into two grids, not one mixed grid, so a multi-tier distributed
  // card's height doesn't stretch every plain single-model card in its row
  // to match it - CSS grid rows default to matching the tallest cell.
  const distributedChains = useMemo(() => filtered.filter((chain) => chain.length > 1), [filtered])
  const singleModels = useMemo(() => filtered.filter((chain) => chain.length === 1), [filtered])
  const chainsByKind: Record<SectionKind, MLModel[][]> = { single: singleModels, distributed: distributedChains }

  // Only sections that actually have something to show, in the user's
  // chosen order - a section with nothing in it never renders (no empty
  // row, no heading), and when only one section has content there's
  // nothing to distinguish it from, so its heading/reorder controls
  // don't render either.
  const visibleSections = sectionOrder.filter((kind) => chainsByKind[kind].length > 0)

  // Standard drag-and-drop reordering: pick up a row by its handle, drop it
  // on another row to move it to that row's position (not just swap the
  // two - written generically in case a third section kind ever exists,
  // though only 2 do today).
  function handleDrop(targetKind: SectionKind) {
    if (draggedKind !== null && draggedKind !== targetKind) {
      setSectionOrder((order) => {
        const next = order.filter((kind) => kind !== draggedKind)
        next.splice(order.indexOf(targetKind), 0, draggedKind)
        return next
      })
    }
    setDraggedKind(null)
    setDragOverKind(null)
  }

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

  function onEdit(id: number) {
    navigate(`/model/${id}`)
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

      {visibleSections.map((kind) => (
        <div key={kind} className="space-y-3">
          {visibleSections.length > 1 && (
            <div
              className={cn(
                'flex items-center gap-1.5 rounded-md border border-transparent px-1 -mx-1',
                draggedKind === kind && 'opacity-40',
                dragOverKind === kind && draggedKind !== kind && 'border-dashed border-primary',
              )}
              draggable
              onDragStart={() => setDraggedKind(kind)}
              onDragEnd={() => {
                setDraggedKind(null)
                setDragOverKind(null)
              }}
              onDragOver={(e) => {
                e.preventDefault()
                setDragOverKind(kind)
              }}
              onDragLeave={() => setDragOverKind((current) => (current === kind ? null : current))}
              onDrop={(e) => {
                e.preventDefault()
                handleDrop(kind)
              }}
            >
              <GripVertical className="size-3.5 shrink-0 cursor-grab text-muted-foreground/60 active:cursor-grabbing" />
              <h2 className="text-sm font-semibold text-muted-foreground">{SECTION_LABEL[kind]}</h2>
            </div>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {chainsByKind[kind].map((chain) => (
              <ModelCard key={chain[0].id} chain={chain} onView={setViewing} onEdit={onEdit} onDelete={confirmDelete} />
            ))}
          </div>
        </div>
      ))}

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
