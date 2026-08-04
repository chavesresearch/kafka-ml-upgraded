import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createVisualizationSocket } from './ws'

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static OPEN = 1
  static CONNECTING = 0

  url: string
  readyState = MockWebSocket.OPEN
  sent: string[] = []
  closeArgs: [number, string] | undefined
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: ((event: unknown) => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close(code: number, reason: string) {
    this.closeArgs = [code, reason]
  }
}

describe('createVisualizationSocket', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('connects to <baseUrl>/ws/ with ws: protocol on http pages', () => {
    createVisualizationSocket({})
    const socket = MockWebSocket.instances[0]
    expect(socket.url).toMatch(/^ws:\/\/.*\/api\/ws\/$/)
  })

  it('forwards incoming messages, errors and close events to the given callbacks', () => {
    const onMessage = vi.fn()
    const onError = vi.fn()
    const onClose = vi.fn()
    createVisualizationSocket({ onMessage, onError, onClose })
    const socket = MockWebSocket.instances[0]

    socket.onmessage?.({ data: 'payload' })
    expect(onMessage).toHaveBeenCalledWith('payload')

    socket.onerror?.('boom')
    expect(onError).toHaveBeenCalledWith('boom')

    socket.onclose?.()
    expect(onClose).toHaveBeenCalled()
  })

  it('sendTopic sends a JSON envelope and returns true when the socket is open', () => {
    const handle = createVisualizationSocket({})
    const ok = handle.sendTopic('mnist-out', true)
    expect(ok).toBe(true)
    const socket = MockWebSocket.instances[0]
    expect(JSON.parse(socket.sent[0])).toEqual({ topic: 'mnist-out', classification: true })
  })

  it('sendTopic returns false without sending when the socket is not open', () => {
    const handle = createVisualizationSocket({})
    MockWebSocket.instances[0].readyState = MockWebSocket.CONNECTING
    const ok = handle.sendTopic('mnist-out', false)
    expect(ok).toBe(false)
    expect(MockWebSocket.instances[0].sent).toHaveLength(0)
  })

  it('close() closes the underlying socket with a normal-closure code', () => {
    const handle = createVisualizationSocket({})
    handle.close()
    expect(MockWebSocket.instances[0].closeArgs).toEqual([1000, 'The user disconnected'])
  })
})
