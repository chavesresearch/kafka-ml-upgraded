// A small, stateful, in-memory fake of the Kafka-ML backend REST API,
// wired in via Playwright route interception (`page.route('**/api/**',
// ...)`). Runs in the test process (Node), not the browser - route
// handler closures share the same JS heap as the test itself, so a test
// can read/mutate `backend.models`/`.results`/etc. directly between
// steps (e.g. to simulate a training Job finishing, which no CI runner
// can do for real without a Kubernetes cluster) with no bridging needed.
//
// Mirrors just enough of the real backend's contract
// (backend/app/controllers/*.py) to drive the frontend through a real
// click-through - not a full backend reimplementation. Same spirit as
// kafkaml-client/tests/conftest.py's FakeBackend, for the same reason:
// a full cluster-backed E2E run isn't something CI can realistically do.
import type { Page, Route } from '@playwright/test'

export interface MockModel {
  id: number
  name: string
  description: string
  imports: string
  code: string
  distributed: boolean
  father: { id: number; name: string; framework: 'tf' | 'pth' } | null
  framework: 'tf' | 'pth'
}

export interface MockConfiguration {
  id: number
  name: string
  description: string
  ml_models: { id: number; name: string; framework: 'tf' | 'pth' }[]
  deployments: { id: number; time: string }[]
}

export interface MockDeployment {
  id: number
  time: string
  configuration: number
  batch: number
  [key: string]: unknown
}

export interface MockResult {
  id: number
  status: 'created' | 'deployed' | 'stopped' | 'finished'
  status_changed: string
  train_metrics: Record<string, number[]> | null
  val_metrics: Record<string, number[]> | null
  test_metrics: Record<string, number[]> | null
  training_time?: number | null
  model: { id: number; name: string; framework: 'tf' | 'pth' }
  deployment: number
}

export interface MockInference {
  id: number
  model_result: number
  replicas: number
  input_format: string
  input_config: string
  input_topic: string
  output_topic: string
  output_upper: string
  limit: number | string | null
  time: string
  status: 'deployed' | 'stopped'
  external_host: string
}

export class MockBackend {
  models: MockModel[] = []
  configurations: MockConfiguration[] = []
  deployments: MockDeployment[] = []
  results: MockResult[] = []
  inferences: MockInference[] = []

  private nextId = { model: 1, configuration: 1, deployment: 1, result: 1, inference: 1 }

  private newId(kind: keyof typeof this.nextId): number {
    return this.nextId[kind]++
  }

  private json(route: Route, status: number, body: unknown) {
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  }

  private empty(route: Route, status: number) {
    return route.fulfill({ status, body: '' })
  }

  private body(route: Route): Record<string, unknown> {
    const raw = route.request().postData()
    return raw ? JSON.parse(raw) : {}
  }

  async handle(route: Route): Promise<void> {
    const request = route.request()
    const method = request.method()
    const url = new URL(request.url())
    // Strip the leading /api the app's own baseUrl prepends.
    const path = url.pathname.replace(/^\/api/, '')

    // -- models -----------------------------------------------------------
    if (path === '/models/' && method === 'GET') return this.json(route, 200, this.models)
    if (path === '/models/distributed' && method === 'GET') {
      return this.json(
        route,
        200,
        this.models.filter((m) => m.distributed).map((m) => ({ id: m.id, name: m.name })),
      )
    }
    if (path === '/models/fathers' && method === 'GET') {
      return this.json(
        route,
        200,
        this.models.filter((m) => m.father === null).map((m) => ({ id: m.id, name: m.name })),
      )
    }
    if (path === '/models/' && method === 'POST') {
      const data = this.body(route)
      const id = this.newId('model')
      const father = data.father != null ? this.models.find((m) => m.id === data.father) : null
      this.models.push({
        id,
        name: data.name as string,
        description: (data.description as string) ?? '',
        imports: (data.imports as string) ?? '',
        code: data.code as string,
        distributed: Boolean(data.distributed),
        father: father ? { id: father.id, name: father.name, framework: father.framework } : null,
        framework: data.framework as 'tf' | 'pth',
      })
      return this.empty(route, 201)
    }
    {
      const m = path.match(/^\/models\/(\d+)$/)
      if (m && method === 'GET') {
        const model = this.models.find((x) => x.id === Number(m[1]))
        return model ? this.json(route, 200, model) : this.json(route, 404, { detail: 'not found' })
      }
      if (m && method === 'DELETE') {
        this.models = this.models.filter((x) => x.id !== Number(m[1]))
        return this.empty(route, 204)
      }
    }

    // -- configurations -----------------------------------------------------
    if (path === '/configurations/' && method === 'GET') return this.json(route, 200, this.configurations)
    if (path === '/configurations/' && method === 'POST') {
      const data = this.body(route)
      const id = this.newId('configuration')
      const modelIds = (data.ml_models as number[]) ?? []
      this.configurations.push({
        id,
        name: data.name as string,
        description: (data.description as string) ?? '',
        ml_models: modelIds
          .map((mid) => this.models.find((m) => m.id === mid))
          .filter((m): m is MockModel => !!m)
          .map((m) => ({ id: m.id, name: m.name, framework: m.framework })),
        deployments: [],
      })
      return this.empty(route, 201)
    }
    {
      const m = path.match(/^\/configurations\/(\d+)$/)
      if (m && method === 'GET') {
        const config = this.configurations.find((c) => c.id === Number(m[1]))
        return config ? this.json(route, 200, config) : this.json(route, 404, { detail: 'not found' })
      }
    }
    {
      const m = path.match(/^\/frameworksInConfiguration\/(\d+)$/)
      if (m && method === 'GET') {
        const config = this.configurations.find((c) => c.id === Number(m[1]))
        const frameworks = [
          ...new Set(
            (config?.ml_models ?? [])
              .map((cm) => this.models.find((mm) => mm.id === cm.id)?.framework)
              .filter((f): f is 'tf' | 'pth' => !!f),
          ),
        ]
        return this.json(route, 200, frameworks)
      }
    }
    {
      const m = path.match(/^\/distributedConfiguration\/(\d+)$/)
      if (m && method === 'GET') {
        const config = this.configurations.find((c) => c.id === Number(m[1]))
        const distributed = (config?.ml_models ?? []).some(
          (cm) => this.models.find((mm) => mm.id === cm.id)?.distributed,
        )
        return this.json(route, 200, distributed)
      }
    }
    {
      const m = path.match(/^\/configurations\/(\d+)$/)
      if (m && method === 'DELETE') {
        this.configurations = this.configurations.filter((x) => x.id !== Number(m[1]))
        return this.empty(route, 204)
      }
    }

    // -- deployments --------------------------------------------------------
    if (path === '/deployments/' && method === 'GET') {
      // Real backend/app/schemas/__init__.py always includes a `results`
      // list on every deployment (never omitted/null, even when empty) -
      // DeploymentList.tsx maps over it unconditionally.
      return this.json(
        route,
        200,
        this.deployments.map((d) => ({ ...d, results: this.results.filter((r) => r.deployment === d.id) })),
      )
    }
    if (path === '/deployments/' && method === 'POST') {
      const data = this.body(route)
      const id = this.newId('deployment')
      const time = new Date().toISOString()
      this.deployments.push({ id, time, configuration: data.configuration as number, batch: data.batch as number, ...data })
      const config = this.configurations.find((c) => c.id === data.configuration)
      if (config) config.deployments.push({ id, time })
      // Mirrors the real platform: a deployment immediately produces one
      // TrainingResult per (root) model in the configuration, starting
      // "created"/"deployed" - the frontend's own ResultList expects this.
      for (const cm of config?.ml_models ?? []) {
        this.results.push({
          id: this.newId('result'),
          status: 'deployed',
          status_changed: time,
          train_metrics: null,
          val_metrics: null,
          test_metrics: null,
          training_time: null,
          model: cm,
          deployment: id,
        })
      }
      return this.empty(route, 201)
    }

    // -- results --------------------------------------------------------------
    if (path === '/results/' && method === 'GET') return this.json(route, 200, this.results)
    {
      const m = path.match(/^\/deployments\/results\/(\d+)$/)
      if (m && method === 'GET') {
        return this.json(
          route,
          200,
          this.results.filter((r) => r.deployment === Number(m[1])),
        )
      }
    }
    {
      const m = path.match(/^\/results\/(\d+)$/)
      if (m && method === 'DELETE') {
        this.results = this.results.filter((x) => x.id !== Number(m[1]))
        return this.empty(route, 204)
      }
    }
    {
      const m = path.match(/^\/results\/stop\/(\d+)$/)
      if (m && method === 'POST') {
        const result = this.results.find((r) => r.id === Number(m[1]))
        if (result) result.status = 'stopped'
        return this.empty(route, 200)
      }
    }

    // -- inference ------------------------------------------------------------
    {
      const m = path.match(/^\/results\/inference\/(\d+)$/)
      if (m && method === 'GET') {
        return this.json(route, 200, { input_format: '', input_config: '' })
      }
      if (m && method === 'POST') {
        const data = this.body(route)
        const id = this.newId('inference')
        this.inferences.push({
          id,
          model_result: Number(m[1]),
          replicas: data.replicas as number,
          input_format: data.input_format as string,
          input_config: data.input_config as string,
          input_topic: data.input_topic as string,
          output_topic: data.output_topic as string,
          output_upper: (data.output_upper as string) ?? '',
          limit: (data.limit as number | string | null) ?? null,
          time: new Date().toISOString(),
          status: 'deployed',
          external_host: (data.external_host as string) ?? '',
        })
        return this.empty(route, 201)
      }
    }
    {
      const m = path.match(/^\/models\/result\/(\d+)$/)
      if (m && method === 'GET') {
        const result = this.results.find((r) => r.id === Number(m[1]))
        const model = result ? this.models.find((mm) => mm.id === result.model.id) : undefined
        return model ? this.json(route, 200, model) : this.json(route, 404, { detail: 'not found' })
      }
    }
    if (path === '/inferences/' && method === 'GET') return this.json(route, 200, this.inferences)
    {
      const m = path.match(/^\/inferences\/(\d+)$/)
      if (m && method === 'DELETE') {
        this.inferences = this.inferences.filter((x) => x.id !== Number(m[1]))
        return this.empty(route, 204)
      }
    }

    // -- datasources / IoT devices (empty by default - not exercised by
    // the golden-path test, but the app's own views GET these on load) --
    if (path === '/datasources/' && method === 'GET') return this.json(route, 200, [])
    if (path === '/devices/' && method === 'GET') return this.json(route, 200, [])

    return this.json(route, 404, { detail: `mock-backend: unhandled ${method} ${path}` })
  }
}

export async function installMockBackend(page: Page): Promise<MockBackend> {
  const backend = new MockBackend()
  await page.route('**/api/**', (route) => backend.handle(route))
  return backend
}
