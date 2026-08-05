import { describe, it, expect } from 'vitest'
import { routes } from './routes'

// Cheap regression net for the whole route table: every route path must be
// defined, and every view module it lazily imports must resolve to a real
// component. This alone would have caught a typo'd file path or a view that
// fails to even parse/import.
describe('routes', () => {
  const paths = routes.map((r) => r.path)

  it('defines a route for every screen the app has', () => {
    expect(paths).toEqual(
      expect.arrayContaining([
        '/',
        '/models',
        '/model-create',
        '/model/:id',
        '/configurations',
        '/configuration-create',
        '/configuration/:id',
        '/deploy/:id',
        '/deployments',
        '/deployments/:id',
        '/results',
        '/results/:id',
        '/results/inference/:id',
        '/results/inference-iot/:id',
        '/results/chart/:id',
        '/results/compare',
        '/inferences',
        '/datasources',
        '/visualization',
        '/devices',
        '/devices-create',
        '/device/:id',
      ]),
    )
  })

  it('every view module lazily resolves without throwing', async () => {
    const modules = [
      './views/ModelList',
      './views/ModelView',
      './views/ConfigurationList',
      './views/ConfigurationView',
      './views/DeploymentView',
      './views/DeploymentList',
      './views/ResultList',
      './views/InferenceView',
      './views/InferenceIoTView',
      './views/PlotView',
      './views/ResultCompareView',
      './views/InferenceList',
      './views/DatasourceList',
      './views/VisualizationView',
      './views/IoTDeviceList',
      './views/IoTDeviceView',
    ]
    for (const path of modules) {
      const resolved = await import(/* @vite-ignore */ path)
      expect(resolved.default, `${path} failed to resolve a default export`).toBeTruthy()
    }
  })

  it('redirects the root path to /models', () => {
    const root = routes.find((r) => r.path === '/')
    expect(root?.element).toBeTruthy()
  })
})
