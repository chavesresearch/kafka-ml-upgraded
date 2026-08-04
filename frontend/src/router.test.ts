import { describe, it, expect } from 'vitest'
import router from './router'

// Cheap regression net for the whole route table: every route's lazy import
// must resolve to a real component. This alone would have caught a typo'd
// file path or a view that fails to even parse/import.
describe('router', () => {
  const paths = router.getRoutes().map((r) => r.path)

  it('defines a route for every screen the Angular app had', () => {
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
        '/inferences',
        '/datasources',
        '/visualization',
        '/devices',
        '/devices-create',
        '/device/:id'
      ])
    )
  })

  it('every route component lazily resolves without throwing', async () => {
    for (const route of router.getRoutes()) {
      if (route.redirect) continue
      const comp = route.components?.default
      const resolved = typeof comp === 'function' ? await (comp as () => Promise<unknown>)() : comp
      expect(resolved, `route ${route.path} failed to resolve a component`).toBeTruthy()
    }
  })

  it('redirects the root path to /models', () => {
    const root = router.getRoutes().find((r) => r.path === '/')
    expect(root?.redirect).toBe('/models')
  })
})
