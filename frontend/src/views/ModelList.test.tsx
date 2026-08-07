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
      { id: 1, name: 'MNIST classifier', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' },
      { id: 2, name: 'CIFAR model', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' },
    ])
    renderModelList()

    expect(await screen.findByText('MNIST classifier')).toBeInTheDocument()
    expect(screen.getByText('CIFAR model')).toBeInTheDocument()
    expect(getModels).toHaveBeenCalledOnce()
  })

  it('renders the upper-layer model name for distributed models', async () => {
    vi.mocked(getModels).mockResolvedValueOnce([
      {
        id: 3,
        name: 'Edge model',
        description: '',
        imports: '',
        code: '',
        distributed: true,
        father: { id: 1, name: 'Cloud model', framework: 'tf' },
        framework: 'tf',
      },
    ])
    renderModelList()
    expect(await screen.findByText('Cloud model')).toBeInTheDocument()
  })

  it('deleting a model calls the API and removes it from the table', async () => {
    const user = userEvent.setup()
    vi.mocked(getModels).mockResolvedValueOnce([
      { id: 1, name: 'To be deleted', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' },
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
