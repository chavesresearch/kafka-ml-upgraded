import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import PrimeVue from 'primevue/config'
import ConfigurationView from './ConfigurationView.vue'

vi.mock('../api', () => ({
  getFatherModels: vi.fn(),
  getConfiguration: vi.fn(),
  createConfiguration: vi.fn(),
  editConfiguration: vi.fn()
}))
vi.mock('../notify', () => ({
  useNotify: () => ({ ok: vi.fn(), error: vi.fn() })
}))

import { getFatherModels, getConfiguration, createConfiguration, editConfiguration } from '../api'

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/configuration-create', component: ConfigurationView },
      { path: '/configuration/:id', component: ConfigurationView },
      { path: '/configurations', component: { template: '<div/>' } }
    ]
  })
  router.push(path)
  await router.isReady()
  const wrapper = mount(ConfigurationView, { global: { plugins: [router, PrimeVue] } })
  await flushPromises()
  return wrapper as VueWrapper<InstanceType<typeof ConfigurationView>>
}

describe('ConfigurationView.vue (create mode)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getFatherModels).mockResolvedValue([
      { id: 1, name: 'Model A', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' },
      { id: 2, name: 'Model B', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' }
    ])
  })

  it('disables submit until a name and at least one model are set', async () => {
    const wrapper = await mountAt('/configuration-create')
    const submit = wrapper.find('button[type="submit"]')
    expect(submit.attributes('disabled')).toBeDefined()

    // Fill in name only -> still invalid without a model selected.
    await wrapper.find('#name').setValue('My configuration')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('submits a create request with the entered name and selected models', async () => {
    vi.mocked(createConfiguration).mockResolvedValueOnce(undefined)
    const wrapper = await mountAt('/configuration-create')

    // Drive the form's reactive state directly: MultiSelect's internal DOM
    // interaction is PrimeVue-specific plumbing not worth re-testing here,
    // the contract under test is "what payload does submit send".
    await wrapper.find('#name').setValue('My configuration')
    wrapper.vm.form.ml_models = [1, 2]
    await wrapper.vm.$nextTick()

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(createConfiguration).toHaveBeenCalledWith({
      name: 'My configuration',
      description: '',
      ml_models: [1, 2]
    })
  })
})

describe('ConfigurationView.vue (edit mode)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getFatherModels).mockResolvedValue([
      { id: 1, name: 'Model A', description: '', imports: '', code: '', distributed: false, father: null, framework: 'tf' }
    ])
  })

  it('loads the existing configuration and normalizes ml_models to ids', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce({
      id: 5,
      name: 'Existing',
      description: 'desc',
      ml_models: [{ id: 1, name: 'Model A' }]
    })
    const wrapper = await mountAt('/configuration/5')
    expect(getConfiguration).toHaveBeenCalledWith(5)
    expect(wrapper.vm.form.ml_models).toEqual([1])
    expect((wrapper.find('#name').element as HTMLInputElement).value).toBe('Existing')
  })

  it('shows an error and hides the submit button when the configuration is not found', async () => {
    vi.mocked(getConfiguration).mockRejectedValueOnce(new Error('not found'))
    const wrapper = await mountAt('/configuration/999')
    expect(wrapper.find('button[type="submit"]').exists()).toBe(false)
  })

  it('submits an edit request to the configuration id from the route', async () => {
    vi.mocked(getConfiguration).mockResolvedValueOnce({
      id: 5,
      name: 'Existing',
      description: '',
      ml_models: [1] as unknown as { id: number; name: string }[]
    })
    vi.mocked(editConfiguration).mockResolvedValueOnce(undefined)
    const wrapper = await mountAt('/configuration/5')

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(editConfiguration).toHaveBeenCalledWith(5, { name: 'Existing', description: '', ml_models: [1] })
  })
})
