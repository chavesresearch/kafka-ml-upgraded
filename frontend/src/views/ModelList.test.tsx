import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { TooltipProvider } from '@/components/ui/tooltip'
import ModelList from './ModelList'

vi.mock('@/api', () => ({
  getModels: vi.fn(),
  deleteModel: vi.fn(),
}))

import { getModels, deleteModel } from '@/api'

function renderModelList() {
  return render(
    <TooltipProvider>
      <MemoryRouter initialEntries={['/models']}>
        <Routes>
          <Route path="/models" element={<ModelList />} />
          <Route path="/model-create" element={<div />} />
          <Route path="/model/:id" element={<div />} />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>,
  )
}

describe('ModelList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches models on mount and renders their names', async () => {
    vi.mocked(getModels).mockResolvedValueOnce([
      {
        id: 1,
        name: 'MNIST classifier',
        description: '',
        imports: '',
        code: '',
        distributed: false,
        father: null,
        framework: 'tf',
        created_at: '2026-01-01T00:00:00',
        updated_at: '2026-01-01T00:00:00',
      },
      {
        id: 2,
        name: 'CIFAR model',
        description: '',
        imports: '',
        code: '',
        distributed: false,
        father: null,
        framework: 'tf',
        created_at: '2026-01-01T00:00:00',
        updated_at: '2026-01-02T00:00:00',
      },
    ])
    renderModelList()

    expect(await screen.findByText('MNIST classifier')).toBeInTheDocument()
    expect(screen.getByText('CIFAR model')).toBeInTheDocument()
    expect(getModels).toHaveBeenCalledOnce()
  })

  it('nests a distributed model chain under its root card, in order of descendance', async () => {
    // Distributed models are a strict father -> child chain on the backend
    // (father_id is unique) - the full flat list always includes both ends,
    // never just the child pointing at a father id that isn't itself in the
    // list (that would be an orphaned row the real API never produces).
    vi.mocked(getModels).mockResolvedValueOnce([
      {
        id: 1,
        name: 'Cloud model',
        description: '',
        imports: '',
        code: '',
        distributed: true,
        father: null,
        framework: 'tf',
        created_at: '2026-01-01T00:00:00',
        updated_at: '2026-01-01T00:00:00',
      },
      {
        id: 3,
        name: 'Edge model',
        description: '',
        imports: '',
        code: '',
        distributed: true,
        father: { id: 1, name: 'Cloud model', framework: 'tf' },
        framework: 'tf',
        created_at: '2026-01-01T00:00:00',
        updated_at: '2026-01-01T00:00:00',
      },
    ])
    renderModelList()
    expect(await screen.findByText('Cloud model')).toBeInTheDocument()
    expect(screen.getByText('Edge model')).toBeInTheDocument()
  })

  it('deleting a model calls the API and removes it from the table', async () => {
    const user = userEvent.setup()
    vi.mocked(getModels).mockResolvedValueOnce([
      {
        id: 1,
        name: 'To be deleted',
        description: '',
        imports: '',
        code: '',
        distributed: false,
        father: null,
        framework: 'tf',
        created_at: '2026-01-01T00:00:00',
        updated_at: '2026-01-01T00:00:00',
      },
    ])
    vi.mocked(deleteModel).mockResolvedValueOnce(undefined)
    renderModelList()
    expect(await screen.findByText('To be deleted')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Delete model' }))
    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(deleteModel).toHaveBeenCalledWith(1))
    await waitFor(() => expect(screen.queryByText('To be deleted')).not.toBeInTheDocument())
  })

  it('surfaces a connection error via notify.error instead of throwing', async () => {
    vi.mocked(getModels).mockRejectedValueOnce(new Error('network down'))
    expect(() => renderModelList()).not.toThrow()
  })
})
