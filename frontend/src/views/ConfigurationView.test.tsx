import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ConfigurationView from './ConfigurationView'

vi.mock('@/api', () => ({
  getFatherModels: vi.fn(),
  getConfiguration: vi.fn(),
  createConfiguration: vi.fn(),
  editConfiguration: vi.fn(),
}))

import { getFatherModels, getConfiguration, createConfiguration, editConfiguration } from '@/api'
import type { MLModel } from '@/types'

function fatherModel(id: number, name: string): MLModel {
  return { id, name, description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/configuration-create" element={<ConfigurationView />} />
        <Route path="/configuration/:id" element={<ConfigurationView />} />
        <Route path="/configurations" element={<div />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ConfigurationView (create mode)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getFatherModels).mockResolvedValue([
      fatherModel(1, 'Model A'),
      fatherModel(2, 'Model B'),
    ])
  })

  it('disables submit until a name and at least one model are set', async () => {
    renderAt('/configuration-create')
    expect(await screen.findByRole('button', { name: 'Create' })).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Name *'), 'My configuration')
    expect(screen.getByRole('button', { name: 'Create' })).toBeDisabled()
  })

  it('submits a create request with the entered name and selected models', async () => {
    const user = userEvent.setup()
    vi.mocked(createConfiguration).mockResolvedValueOnce(undefined)
    renderAt('/configuration-create')
    await screen.findByRole('combobox')

    await user.type(screen.getByLabelText('Name *'), 'My configuration')
    await user.click(screen.getByRole('combobox'))
    await user.click(await screen.findByText('ID1 Model A'))
    await user.click(screen.getByText('ID2 Model B'))
    await user.keyboard('{Escape}')

    await user.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() =>
      expect(createConfiguration).toHaveBeenCalledWith({
        name: 'My configuration',
        description: '',
        ml_models: [1, 2],
      }),
    )
  })
})

describe('ConfigurationView (edit mode)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getFatherModels).mockResolvedValue([fatherModel(1, 'Model A')])
  })

  it('loads the existing configuration and normalizes ml_models to ids', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce({
      id: 5,
      name: 'Existing',
      description: 'desc',
      ml_models: [fatherModel(1, 'Model A')],
    })
    renderAt('/configuration/5')

    expect(await screen.findByDisplayValue('Existing')).toBeInTheDocument()
    expect(getConfiguration).toHaveBeenCalledWith(5)
  })

  it('shows an error and hides the submit button when the configuration is not found', async () => {
    vi.mocked(getConfiguration).mockRejectedValueOnce(new Error('not found'))
    renderAt('/configuration/999')

    await waitFor(() => expect(getConfiguration).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
  })

  it('submits an edit request to the configuration id from the route', async () => {
    const user = userEvent.setup()
    vi.mocked(getConfiguration).mockResolvedValueOnce({
      id: 5,
      name: 'Existing',
      description: '',
      ml_models: [1] as unknown as { id: number; name: string; framework: 'tf' }[],
    })
    vi.mocked(editConfiguration).mockResolvedValueOnce(undefined)
    renderAt('/configuration/5')

    const submit = await screen.findByRole('button', { name: 'Edit' })
    await user.click(submit)

    await waitFor(() =>
      expect(editConfiguration).toHaveBeenCalledWith(5, { name: 'Existing', description: '', ml_models: [1] }),
    )
  })
})
