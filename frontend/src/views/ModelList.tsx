import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ColumnDef } from '@tanstack/react-table'
import { Eye, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import DataTable from '@/components/DataTable'
import { useConfirm } from '@/hooks/useConfirm'
import { getModels, deleteModel } from '@/api'
import { useNotify } from '@/notify'
import { truncate } from '@/logic/format'
import type { MLModel } from '@/types'

export default function ModelList() {
  const notify = useNotify()
  const { confirm, dialog } = useConfirm()
  const [models, setModels] = useState<MLModel[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getModels()
      .then(setModels)
      .catch(() => notify.error('Error connecting with the server'))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  const columns: ColumnDef<MLModel, unknown>[] = [
    { accessorKey: 'id', header: 'ID' },
    { accessorKey: 'name', header: 'Name' },
    { accessorKey: 'description', header: 'Description', enableSorting: false },
    {
      id: 'imports',
      header: 'Imports',
      enableSorting: false,
      cell: ({ row }) => <span title={row.original.imports}>{truncate(row.original.imports, 20)}</span>,
    },
    {
      id: 'code',
      header: 'Code',
      enableSorting: false,
      cell: ({ row }) => <span title={row.original.code}>{truncate(row.original.code, 20)}</span>,
    },
    {
      accessorKey: 'distributed',
      header: 'Distributed',
      cell: ({ row }) => (row.original.distributed ? 'true' : 'false'),
    },
    {
      id: 'father',
      header: 'Upper layer',
      enableSorting: false,
      cell: ({ row }) => row.original.father?.name ?? '',
    },
    {
      id: 'actions',
      header: 'Actions',
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" title="View/edit model" asChild>
            <Link to={`/model/${row.original.id}`}>
              <Eye className="size-4" />
            </Link>
          </Button>
          <Button variant="ghost" size="icon" title="Delete model" onClick={() => confirmDelete(row.original.id)}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Models</h1>
        <span className="flex-1" />
        <Button size="icon" className="rounded-full" title="Add a model" asChild>
          <Link to="/model-create">
            <Plus className="size-4" />
          </Link>
        </Button>
      </div>

      <DataTable columns={columns} data={models} getRowId={(m) => String(m.id)} loading={loading} />
      {dialog}
    </div>
  )
}
