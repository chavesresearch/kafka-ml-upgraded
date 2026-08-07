import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ImportDeploymentView from './ImportDeploymentView'

vi.mock('@/api', () => ({
  getConfiguration: vi.fn(),
  getDistributedConfiguration: vi.fn(),
  importDeployment: vi.fn(),
}))

import { getConfiguration, getDistributedConfiguration, importDeployment } from '@/api'
import type { Configuration } from '@/types'

function configuration(overrides: Partial<Configuration> = {}): Configuration {
  return {
    id: 1,
    name: 'my-config',
    description: '',
    ml_models: [{ id: 5, name: 'my-model', framework: 'tf' }],
    ...overrides,
  }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/import/:id" element={<ImportDeploymentView />} />
        <Route path="/deployments/:id" element={<div>deployments page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ImportDeploymentView', () => {
  it('shows the single model and its framework once loaded', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce(configuration())
    vi.mocked(getDistributedConfiguration).mockResolvedValueOnce(false)

    renderAt('/import/1')

    expect(await screen.findByText('my-model')).toBeInTheDocument()
    expect(screen.getByText('(tf)')).toBeInTheDocument()
    expect(screen.getByText(/Trained model file \(\.h5\)/)).toBeInTheDocument()
  })

  it('shows .pth for a PyTorch model', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce(
      configuration({ ml_models: [{ id: 5, name: 'my-pth-model', framework: 'pth' }] }),
    )
    vi.mocked(getDistributedConfiguration).mockResolvedValueOnce(false)

    renderAt('/import/1')

    expect(await screen.findByText(/Trained model file \(\.pth\)/)).toBeInTheDocument()
  })

  it('rejects a distributed configuration with an explanatory message, no form shown', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce(
      configuration({ ml_models: [{ id: 5, name: 'father', framework: 'tf' }, { id: 6, name: 'child', framework: 'tf' }] }),
    )
    vi.mocked(getDistributedConfiguration).mockResolvedValueOnce(true)

    renderAt('/import/1')

    expect(await screen.findByText(/not supported for distributed configurations/)).toBeInTheDocument()
    expect(screen.queryByText(/Trained model file/)).not.toBeInTheDocument()
  })

  it('rejects a multi-model (non-distributed) configuration too', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce(
      configuration({ ml_models: [{ id: 5, name: 'a', framework: 'tf' }, { id: 6, name: 'b', framework: 'tf' }] }),
    )
    vi.mocked(getDistributedConfiguration).mockResolvedValueOnce(false)

    renderAt('/import/1')

    expect(await screen.findByText(/exactly one model/)).toBeInTheDocument()
  })

  it('disables Import until a file is chosen', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce(configuration())
    vi.mocked(getDistributedConfiguration).mockResolvedValueOnce(false)

    renderAt('/import/1')
    await screen.findByText('my-model')

    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled()
  })

  it('submits the file and parsed metrics, then navigates to the deployment list', async () => {
    const user = userEvent.setup()
    vi.mocked(getConfiguration).mockResolvedValueOnce(configuration())
    vi.mocked(getDistributedConfiguration).mockResolvedValueOnce(false)
    vi.mocked(importDeployment).mockResolvedValueOnce(undefined)

    renderAt('/import/1')
    await screen.findByText('my-model')

    const file = new File([new Uint8Array([1, 2, 3])], 'model.h5', { type: 'application/octet-stream' })
    const fileInput = document.querySelector('input[type=file]') as HTMLInputElement
    await user.upload(fileInput, file)

    // fireEvent.change, not userEvent.type - userEvent's .type() parses
    // {}/[] as key-modifier syntax, which JSON content is full of.
    fireEvent.change(screen.getByLabelText(/Train metrics/), { target: { value: '{"accuracy": [0.9]}' } })
    await user.type(screen.getByLabelText(/Training time/), '12.5')

    await user.click(screen.getByRole('button', { name: 'Import' }))

    await waitFor(() => expect(importDeployment).toHaveBeenCalledTimes(1))
    const [configId, uploadedFile, metrics] = vi.mocked(importDeployment).mock.calls[0]
    expect(configId).toBe(1)
    expect(uploadedFile).toBe(file)
    expect(metrics).toEqual({ train_metrics: { accuracy: [0.9] }, training_time: 12.5 })

    expect(await screen.findByText('deployments page')).toBeInTheDocument()
  })

  it('shows an error and does not submit when metrics JSON is invalid', async () => {
    const user = userEvent.setup()
    vi.mocked(getConfiguration).mockResolvedValueOnce(configuration())
    vi.mocked(getDistributedConfiguration).mockResolvedValueOnce(false)

    renderAt('/import/1')
    await screen.findByText('my-model')

    const file = new File([new Uint8Array([1])], 'model.h5')
    const fileInput = document.querySelector('input[type=file]') as HTMLInputElement
    await user.upload(fileInput, file)
    await user.type(screen.getByLabelText(/Train metrics/), 'not json')

    await user.click(screen.getByRole('button', { name: 'Import' }))

    expect(importDeployment).not.toHaveBeenCalled()
  })
})
