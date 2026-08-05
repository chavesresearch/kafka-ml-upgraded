import { useEffect, useRef, useState } from 'react'
import { Bar, BarChart, Cell, Line, LineChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { Send, X, Tag } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import CodeEditor from '@/components/CodeEditor'
import { createVisualizationSocket, type VisualizationSocket } from '@/ws'
import { useNotify } from '@/notify'
import {
  INIT_COLOR,
  createClassificationState,
  applyClassificationMessage,
  classificationBarData,
  createRegressionState,
  applyRegressionMessage,
  regressionLineData,
  type ClassificationState,
  type RegressionState,
  type VisualizationConfig,
} from '@/logic/visualization'
import type { ChartDataShape } from '@/types'

function toRechartsData(shape: ChartDataShape): Record<string, string | number>[] {
  return shape.labels.map((label, i) => {
    const row: Record<string, string | number> = { x: label }
    for (const dataset of shape.datasets) row[dataset.label] = dataset.data[i]
    return row
  })
}

export default function VisualizationView() {
  const notify = useNotify()

  const [config, setConfig] = useState('')
  const [topic, setTopic] = useState('')
  const [isClassification, setIsClassification] = useState(false)
  const [isRegression, setIsRegression] = useState(false)
  const [connected, setConnected] = useState(false)
  const [topicConfigured, setTopicConfigured] = useState(false)

  const [workingCondition, setWorkingCondition] = useState('')
  const [currentColor, setCurrentColor] = useState(INIT_COLOR)
  const [lastStatuses, setLastStatuses] = useState<{ label: string; color: string }[]>([])
  const [barData, setBarData] = useState<ChartDataShape | null>(null)
  const [lineData, setLineData] = useState<ChartDataShape | null>(null)

  // Kept as plain refs, not React state: the classification/regression state
  // machines (src/logic/visualization.ts) are mutated in place on every
  // WebSocket message; only their rendered output is pushed into state above.
  const classificationStateRef = useRef<ClassificationState | null>(null)
  const regressionStateRef = useRef<RegressionState | null>(null)
  const socketRef = useRef<VisualizationSocket | null>(null)
  const isClassificationRef = useRef(false)
  const isRegressionRef = useRef(false)

  function syncClassificationView() {
    const state = classificationStateRef.current
    if (!state) return
    setWorkingCondition(state.workingCondition)
    setCurrentColor(state.currentColor)
    setLastStatuses(state.lastStatuses)
    setBarData(classificationBarData(state))
  }

  function onClassificationData(data: string) {
    if (!classificationStateRef.current) return
    applyClassificationMessage(classificationStateRef.current, data)
    syncClassificationView()
  }

  function onRegressionData(data: string) {
    if (!regressionStateRef.current) return
    applyRegressionMessage(regressionStateRef.current, data)
    setLineData(regressionLineData(regressionStateRef.current))
  }

  function setConfigHandler() {
    try {
      const parsed = JSON.parse(config) as VisualizationConfig
      closeWS()
      setIsClassification(false)
      setIsRegression(false)
      if (parsed.type === 'classification') {
        classificationStateRef.current = createClassificationState(parsed)
        isClassificationRef.current = true
        isRegressionRef.current = false
        syncClassificationView()
        setIsClassification(true)
      } else if (parsed.type === 'regression') {
        regressionStateRef.current = createRegressionState(parsed)
        isClassificationRef.current = false
        isRegressionRef.current = true
        setLineData(regressionLineData(regressionStateRef.current))
        setIsRegression(true)
      } else {
        throw new Error('Type not recognized, available types: classification and regression')
      }
      notify.ok('Configuration set correctly')
    } catch (e) {
      notify.error(`Configuration not valid: [${e}]`)
    }
  }

  function sendTopic() {
    if (!connected) {
      const socket = createVisualizationSocket({
        onMessage: (data) => {
          if (isClassificationRef.current) onClassificationData(data)
          else if (isRegressionRef.current) onRegressionData(data)
        },
        onError: () => {
          notify.error('Error connecting with the server')
          setConnected(false)
        },
        onClose: () => {
          setConnected(false)
          setTopicConfigured(false)
        },
      })
      socketRef.current = socket
      setConnected(true)
    }
    // Give the socket a moment to open before subscribing (as the original app did).
    setTimeout(() => {
      if (socketRef.current && socketRef.current.sendTopic(topic, isClassificationRef.current)) {
        notify.ok('Connected to topic: ' + topic)
        setTopicConfigured(true)
      } else {
        notify.error('Error sending the message')
      }
    }, 1000)
  }

  function closeWS() {
    if (socketRef.current) {
      socketRef.current.close()
      socketRef.current = null
      setConnected(false)
      setTopicConfigured(false)
    }
  }

  useEffect(() => closeWS, [])

  const barShape = barData
  const barChartData = barShape ? toRechartsData(barShape) : []
  const barConfig: ChartConfig = barShape
    ? { Average: { label: 'Average', color: barShape.datasets[0]?.backgroundColor as string } }
    : {}

  const lineShape = lineData
  const lineChartData = lineShape ? toRechartsData(lineShape) : []
  const lineConfig: ChartConfig = lineShape
    ? Object.fromEntries(lineShape.datasets.map((d) => [d.label, { label: d.label, color: d.borderColor }]))
    : {}

  return (
    <div className="space-y-5">
      <div className="max-w-2xl space-y-1.5">
        <Label>Label config</Label>
        <CodeEditor
          value={config}
          onChange={setConfig}
          language="plaintext"
          height="140px"
          placeholder={'{\n  "type": "classification",\n  "labels": [...]\n}'}
          ariaLabel="Label config"
        />
        <div className="pt-1">
          <Button variant="outline" onClick={setConfigHandler}>
            <Tag /> Set configuration
          </Button>
        </div>
      </div>

      {(isClassification || isRegression) && (
        <div className="max-w-2xl space-y-1.5">
          <Label>Kafka output topic</Label>
          <div className="flex gap-2">
            <Input value={topic} onChange={(e) => setTopic(e.target.value)} disabled={connected || topicConfigured} />
            <Button variant="outline" size="icon" title="Connect to topic" disabled={connected || topicConfigured} onClick={sendTopic}>
              <Send className="size-4" />
            </Button>
            {connected && (
              <Button variant="outline" size="icon" title="Disconnect" onClick={closeWS}>
                <X className="size-4" />
              </Button>
            )}
          </div>
        </div>
      )}

      {isClassification && (
        <>
          <h2 className="text-base font-semibold">Current status</h2>
          <div
            className="flex h-[200px] items-center justify-center rounded-lg shadow-sm"
            style={{ backgroundColor: currentColor }}
          >
            <p className="text-2xl font-bold">{workingCondition}</p>
          </div>

          <h2 className="text-base font-semibold">Last status</h2>
          <div className="flex gap-2">
            {lastStatuses.map((status, i) => (
              <div
                key={i}
                className="flex min-h-12 flex-1 items-center justify-center rounded-md font-semibold"
                style={{ backgroundColor: status.color }}
              >
                {status.label}
              </div>
            ))}
          </div>

          <h2 className="text-base font-semibold">Average</h2>
          {barData && (
            <div className="rounded-lg border bg-card p-5">
              <ChartContainer config={barConfig} className="h-[320px] w-full">
                <BarChart data={barChartData}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="x" />
                  <YAxis domain={[0, 1]} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="Average" isAnimationActive={false}>
                    {barChartData.map((_, i) => {
                      const colors = barShape?.datasets[0]?.backgroundColor
                      const fill = Array.isArray(colors) ? colors[i] : (colors ?? INIT_COLOR)
                      return <Cell key={i} fill={fill} />
                    })}
                  </Bar>
                </BarChart>
              </ChartContainer>
            </div>
          )}
        </>
      )}

      {isRegression && lineData && (
        <div className="mt-2 rounded-lg border bg-card p-5">
          <ChartContainer config={lineConfig} className="h-[400px] w-full">
            <LineChart data={lineChartData}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" />
              <YAxis />
              <ChartTooltip content={<ChartTooltipContent />} />
              {lineData.datasets.map((d) => (
                <Line key={d.label} type="monotone" dataKey={d.label} stroke={d.borderColor} dot={false} strokeWidth={2} isAnimationActive={false} />
              ))}
            </LineChart>
          </ChartContainer>
        </div>
      )}
    </div>
  )
}
