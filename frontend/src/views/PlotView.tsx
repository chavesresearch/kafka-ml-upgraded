import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Line, LineChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { Download, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import MultiSelect from '@/components/MultiSelect'
import { getChartInfo, getConfusionMatrix, downloadJSON } from '@/api'
import { useNotify } from '@/notify'
import { availableMetricNames, buildChartData, toRechartsData } from '@/logic/plot'
import type { ChartMetric } from '@/types'

// Same palette as the original Angular/Vue plot view.
const COLORS = [
  '#FF3333', '#FF33FF', '#CC33FF', '#0000FF', '#33CCFF',
  '#33FFFF', '#33FF66', '#CCFF33', '#FFCC00', '#FF6600',
]

export default function PlotView() {
  const { id } = useParams()
  const notify = useNotify()

  const resultID = Number(id)
  const [metricsRetrieved, setMetricsRetrieved] = useState<ChartMetric[]>([])
  const [confMatrixRetrieved, setConfMatrixRetrieved] = useState<unknown>(null)
  const [availableMetrics, setAvailableMetrics] = useState<string[]>([])
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([])
  const [confusionMatrixUrl, setConfusionMatrixUrl] = useState<string | null>(null)
  // The blob URL refreshData last created, so a later call can revoke it
  // before creating a new one instead of leaking it (URL.createObjectURL
  // holds the blob in memory until explicitly revoked - api.ts's own
  // downloadBlob already does this, this view never did).
  const confusionMatrixUrlRef = useRef<string | null>(null)

  const refreshData = useCallback(
    async (isCancelled?: () => boolean) => {
      try {
        const data = await getChartInfo(resultID)
        if (isCancelled?.()) return
        const metrics = data.metrics || []
        setMetricsRetrieved(metrics)
        // Offer only base metric names; picking one also plots its "<name>_val" series.
        const names = availableMetricNames(metrics)
        setAvailableMetrics(names)
        // Auto-select everything on first load so the chart isn't blank with
        // no indication a metric needs picking - but don't clobber a
        // deliberate selection the user already narrowed down to on a
        // manual Refresh click.
        setSelectedMetrics((current) => (current.length === 0 ? names : current))
        setConfMatrixRetrieved(data.conf_mat)

        if (data.conf_mat != null) {
          const { blob } = await getConfusionMatrix(resultID)
          if (isCancelled?.()) return
          if (confusionMatrixUrlRef.current) URL.revokeObjectURL(confusionMatrixUrlRef.current)
          const url = URL.createObjectURL(blob)
          confusionMatrixUrlRef.current = url
          setConfusionMatrixUrl(url)
        }
      } catch {
        if (!isCancelled?.()) notify.error('The training result does not exist')
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resultID],
  )

  // Guards against a fast route change (e.g. clicking between two results'
  // chart pages quickly) letting an older result's response land after a
  // newer one's and overwrite it with stale data - same `cancelled`
  // pattern every other detail view in this app already uses for its own
  // mount/id-change fetch effect (this one just never had it).
  useEffect(() => {
    let cancelled = false
    refreshData(() => cancelled)
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultID])

  // Revoke whatever blob URL is still outstanding when this view unmounts
  // entirely (navigating away, not just switching :id or clicking Refresh -
  // both of those are already covered above, by revoking-before-replacing).
  useEffect(() => {
    return () => {
      if (confusionMatrixUrlRef.current) URL.revokeObjectURL(confusionMatrixUrlRef.current)
    }
  }, [])

  const chartShape = useMemo(
    () => buildChartData(metricsRetrieved, selectedMetrics, COLORS),
    [metricsRetrieved, selectedMetrics],
  )

  const chartData = useMemo(() => (chartShape ? toRechartsData(chartShape) : []), [chartShape])

  const chartConfig = useMemo<ChartConfig>(() => {
    if (!chartShape) return {}
    return Object.fromEntries(
      chartShape.datasets.map((d) => [d.label, { label: d.label, color: d.borderColor }]),
    )
  }, [chartShape])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Training result {resultID} — Metrics charts</h1>
        <span className="flex-1" />
        <Button variant="ghost" size="icon" title="Refresh" onClick={() => refreshData()}>
          <RefreshCw className="size-4" />
        </Button>
      </div>

      <div className="max-w-md space-y-1.5">
        <Label>Select Metrics</Label>
        <MultiSelect
          options={availableMetrics.map((m) => ({ value: m, label: m }))}
          value={selectedMetrics}
          onChange={setSelectedMetrics}
          placeholder="Select metrics"
        />
      </div>

      {chartShape && (
        <div className="rounded-lg border bg-card p-5">
          <ChartContainer config={chartConfig} className="h-[400px] w-full">
            <LineChart data={chartData}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="x" label={{ value: 'Epochs', position: 'insideBottom', offset: -5 }} />
              <YAxis />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              {chartShape.datasets.map((d) => (
                <Line
                  key={d.label}
                  type="monotone"
                  dataKey={d.label}
                  stroke={d.borderColor}
                  dot={false}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ChartContainer>
        </div>
      )}

      <div>
        <Button variant="outline" onClick={() => downloadJSON(metricsRetrieved, 'metrics.json')}>
          <Download /> Download Metrics in JSON Format
        </Button>
      </div>

      {confMatrixRetrieved != null && (
        <div className="space-y-3">
          {confusionMatrixUrl && (
            <img src={confusionMatrixUrl} alt="Confusion Matrix" className="max-w-full rounded-lg" />
          )}
          <Button variant="outline" onClick={() => downloadJSON(confMatrixRetrieved, 'conf_matrix.json')}>
            <Download /> Download Confusion Matrix in JSON Format
          </Button>
        </div>
      )}
    </div>
  )
}
