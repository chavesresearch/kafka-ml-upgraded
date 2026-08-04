import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as api from './api'

function jsonResponse(body: unknown, { ok = true, status = 200, statusText = 'OK' } = {}) {
  return {
    ok,
    status,
    statusText,
    headers: { get: (name: string) => (name === 'Content-Type' ? 'application/json' : null) },
    json: async () => body,
    text: async () => JSON.stringify(body)
  } as unknown as Response
}

function errorResponse(text: string, { status = 400, statusText = 'Bad Request' } = {}) {
  return {
    ok: false,
    status,
    statusText,
    headers: { get: () => 'text/plain' },
    text: async () => text
  } as unknown as Response
}

describe('api.ts REST client', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs the correct path and parses JSON', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse([{ id: 1, name: 'Model' }]))
    const models = await api.getModels()
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/models/', { method: 'GET', headers: {} })
    expect(models).toEqual([{ id: 1, name: 'Model' }])
  })

  it('POSTs a JSON body with the correct content type', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse({}))
    await api.createModel({ name: 'foo', description: '', framework: 'tf', imports: '', code: '' })
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/models/',
      expect.objectContaining({ method: 'POST', headers: { 'Content-Type': 'application/json' } })
    )
  })

  it('builds nested resource paths correctly', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse({}))
    await api.getModel(42)
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/models/42', { method: 'GET', headers: {} })

    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse([]))
    await api.getDistributedModels()
    expect(globalThis.fetch).toHaveBeenLastCalledWith('/api/models/distributed', {
      method: 'GET',
      headers: {}
    })
  })

  it('PUTs edits and DELETEs by id', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse({}))
    await api.editModel(3, { name: 'renamed', description: '', framework: 'tf', imports: '', code: '' })
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/models/3',
      expect.objectContaining({ method: 'PUT' })
    )

    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse({}))
    await api.deleteModel(3)
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/models/3', { method: 'DELETE', headers: {} })
  })

  it('rejects with the response body text when the server returns an error', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(errorResponse('Information not valid'))
    await expect(
      api.createModel({ name: 'bad', description: '', framework: 'tf', imports: '', code: '' })
    ).rejects.toThrow('Information not valid')
  })

  it('falls back to status text when the error body is empty', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      errorResponse('', { status: 500, statusText: 'Server Error' })
    )
    await expect(api.getModels()).rejects.toThrow('500 Server Error')
  })

  it('the IoT inference endpoint posts to /results/inference-iot/{id}', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse({}))
    await api.deployIoTInference(9, { code: 'x', device_token: ['t1'], model_result: 9, applyIntQuant: false })
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/results/inference-iot/9',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('getTrainedModel resolves the blob and headers, and rejects on failure', async () => {
    const blob = new Blob(['binary'])
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: true,
      headers: { get: (name: string) => (name === 'ML-Framework' ? 'tf' : null) },
      blob: async () => blob
    } as unknown as Response)
    const result = await api.getTrainedModel(5)
    expect(result.blob).toBe(blob)
    expect(result.headers.get('ML-Framework')).toBe('tf')

    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found'
    } as unknown as Response)
    await expect(api.getTrainedModel(999)).rejects.toThrow('404 Not Found')
  })
})

describe('downloadBlob / downloadJSON', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('creates an object URL, triggers a click with the given filename, then revokes it', () => {
    const createObjectURL = vi.fn(() => 'blob:mock-url')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })

    const clickSpy = vi.fn()
    const anchor = { click: clickSpy, href: '', download: '' } as unknown as HTMLAnchorElement
    vi.spyOn(document, 'createElement').mockReturnValue(anchor as any)

    api.downloadBlob(new Blob(['data']), 'result.json')

    expect(createObjectURL).toHaveBeenCalled()
    expect(anchor.download).toBe('result.json')
    expect(anchor.href).toBe('blob:mock-url')
    expect(clickSpy).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
  })

  it('downloadJSON serializes the value into a Blob download', () => {
    const createObjectURL = vi.fn(() => 'blob:mock-url')
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL: vi.fn() })
    const anchor = { click: vi.fn(), href: '', download: '' } as unknown as HTMLAnchorElement
    vi.spyOn(document, 'createElement').mockReturnValue(anchor as any)

    api.downloadJSON({ a: 1 }, 'metrics.json')

    expect(anchor.download).toBe('metrics.json')
    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
  })
})
