// WebSocket helper for the Visualization view.
// Mirrors visualization-ws.service.ts: connects to <baseUrl>/ws/ upgrading
// http(s) -> ws(s), then sends {topic, classification} to subscribe.
import { baseUrl } from './env'

export interface VisualizationSocketHandlers {
  onMessage?: (data: string) => void
  onError?: (event: Event) => void
  onClose?: () => void
}

export interface VisualizationSocket {
  // Returns false if the socket is not open yet.
  sendTopic(topic: string, isClassification: boolean): boolean
  close(): void
}

export function createVisualizationSocket({
  onMessage,
  onError,
  onClose
}: VisualizationSocketHandlers): VisualizationSocket {
  const url = new URL(baseUrl + '/ws/', window.location.href)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'

  const ws = new WebSocket(url.toString())
  ws.onmessage = (event) => onMessage && onMessage(event.data as string)
  ws.onerror = (event) => onError && onError(event)
  ws.onclose = () => onClose && onClose()

  return {
    sendTopic(topic: string, isClassification: boolean): boolean {
      if (ws.readyState !== WebSocket.OPEN) return false
      ws.send(JSON.stringify({ topic, classification: isClassification }))
      return true
    },
    close() {
      ws.close(1000, 'The user disconnected')
    }
  }
}
