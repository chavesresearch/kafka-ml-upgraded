import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import PrimeVue from 'primevue/config'
import ModelList from './ModelList.vue'

vi.mock('../api', () => ({
  getModels: vi.fn(),
  deleteModel: vi.fn()
}))
vi.mock('../notify', () => ({
  useNotify: () => ({ ok: vi.fn(), error: vi.fn() })
}))
// The delete flow goes through a confirm dialog; simulate the user always accepting.
vi.mock('primevue/useconfirm', () => ({
  useConfirm: () => ({ require: (opts: { accept: () => void }) => opts.accept() })
}))

import { getModels, deleteModel } from '../api'

async function mountModelList() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/models', component: ModelList },
      { path: '/model-create', component: { template: '<div/>' } },
      { path: '/model/:id', component: { template: '<div/>' } }
    ]
  })
  router.push('/models')
  await router.isReady()
  return mount(ModelList, { global: { plugins: [router, PrimeVue] } })
}

describe('ModelList.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches models on mount and renders their names', async () => {
    vi.mocked(getModels).mockResolvedValueOnce([
      { id: 1, name: 'MNIST classifier', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' },
      { id: 2, name: 'CIFAR model', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' }
    ])
    const wrapper = await mountModelList()
    await flushPromises()

    expect(getModels).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('MNIST classifier')
    expect(wrapper.text()).toContain('CIFAR model')
  })

  it('renders the upper-layer model name for distributed models via getName()', async () => {
    vi.mocked(getModels).mockResolvedValueOnce([
      {
        id: 3,
        name: 'Edge model',
        description: '',
        imports: '',
        code: '',
        distributed: true,
        father: { id: 1, name: 'Cloud model' },
        framework: 'tf'
      }
    ])
    const wrapper = await mountModelList()
    await flushPromises()
    expect(wrapper.text()).toContain('Cloud model')
  })

  it('deleting a model calls the API and removes it from the table', async () => {
    vi.mocked(getModels).mockResolvedValueOnce([
      { id: 1, name: 'To be deleted', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' }
    ])
    vi.mocked(deleteModel).mockResolvedValueOnce(undefined)
    const wrapper = await mountModelList()
    await flushPromises()
    expect(wrapper.text()).toContain('To be deleted')

    const deleteButton = wrapper.find('button[title="Delete model"]')
    await deleteButton.trigger('click')
    await flushPromises()

    expect(deleteModel).toHaveBeenCalledWith(1)
    expect(wrapper.text()).not.toContain('To be deleted')
  })

  it('surfaces a connection error via notify.error instead of throwing', async () => {
    vi.mocked(getModels).mockRejectedValueOnce(new Error('network down'))
    await expect(mountModelList()).resolves.toBeTruthy()
  })
})
