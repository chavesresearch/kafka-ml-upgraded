// Overlays several training results' metric curves side by side - one facet
// (chart) per metric, one line per (result, split). See logic/plot.ts's
// buildComparisonChartData for the data-shaping/color-assignment rules.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Line, LineChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import { Download, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import MultiSelect from '@/components/MultiSelect'
import MetricsTable from '@/components/MetricsTable'
import { getResults, getChartInfo, downloadJSON } from '@/api'
import { useNotify } from '@/notify'
import { buildMetricsTable } from '@/logic/format'
import {
  MAX_COMPARE_RESULTS,
  parseCompareIds,
  availableComparisonMetricNames,
  buildComparisonChartData,
  toRechartsData,
  type ComparisonResultMetrics,
} from '@/logic/plot'
import type { TrainingResult } from '@/types'

// Tied to index.css's 5-slot theme-aware chart palette (--chart-1..--chart-5).
function colorForIndex(i: number): string {
  return `var(--chart-${(i % 5) + 1})`
}

export default function ResultCompareView() {
  const [searchParams, setSearchParams] = useSearchParams()
  const notify = useNotify()

  // Not just the MultiSelect picker's own guard - a hand-typed URL with more
  // than MAX_COMPARE_RESULTS ids would otherwise still reach buildComparisonChartData/
  // resultColors below, wrapping the 5-slot palette around and colliding two
  // results onto the same color rather than being rejected outright.
  const parsedIds = useMemo(() => parseCompareIds(searchParams.get('ids')), [searchParams])
  const ids = useMemo(() => parsedIds.slice(0, MAX_COMPARE_RESULTS), [parsedIds])

  const [allResults, setAllResults] = useState<TrainingResult[]>([])
  const [comparisonMetrics, setComparisonMetrics] = useState<ComparisonResultMetrics[]>([])
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([])

  useEffect(() => {
    if (parsedIds.length > MAX_COMPARE_RESULTS) {
      notify.error(`Only the first ${MAX_COMPARE_RESULTS} results in the URL are compared`)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parsedIds])

  // Position within `ids` (selection order), not `compared` below - a result
  // that fails to load shouldn't reshuffle every other result's color.
  const resultColors = useMemo(() => {
    const colors: Record<number, string> = {}
    ids.forEach((id, i) => {
      colors[id] = colorForIndex(i)
    })
    return colors
  }, [ids])

  const compared = useMemo(
    () => ids.map((id) => allResults.find((r) => r.id === id)).filter((r): r is TrainingResult => r != null),
    [ids, allResults],
  )

  const refreshData = useCallback(async () => {
    try {
      const results = await getResults()
      setAllResults(results)

      const found = ids.map((id) => results.find((r) => r.id === id)).filter((r): r is TrainingResult => r != null)
      const missing = ids.filter((id) => !results.some((r) => r.id === id))
      if (missing.length > 0) {
        notify.error(`Result${missing.length > 1 ? 's' : ''} not found: ${missing.join(', ')}`)
      }

      const settled = await Promise.allSettled(found.map((r) => getChartInfo(r.id)))
      const metrics: ComparisonResultMetrics[] = settled.map((outcome, i) => {
        const result = found[i]
        const resultLabel = `Result ${result.id} — ${result.model.name}`
        if (outcome.status === 'fulfilled') {
          return { resultId: result.id, resultLabel, metrics: outcome.value.metrics ?? [] }
        }
        notify.error(`Could not load metrics for Result ${result.id}`)
        return { resultId: result.id, resultLabel, metrics: [] }
      })
      setComparisonMetrics(metrics)
      // Auto-select everything on first load, same UX PlotView already has -
      // don't clobber a deliberate narrower selection on a manual Refresh.
      const names = availableComparisonMetricNames(metrics)
      setSelectedMetrics((current) => (current.length === 0 ? names : current))
    } catch {
      notify.error('Error connecting with the server')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids])

  useEffect(() => {
    refreshData()
  }, [refreshData])

  function updateCompareSelection(next: string[]) {
    if (next.length > MAX_COMPARE_RESULTS) {
      notify.error(`You can compare up to ${MAX_COMPARE_RESULTS} results at once`)
      return
    }
    setSearchParams(next.length > 0 ? { ids: next.join(',') } : {})
  }

  if (ids.length < 2) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Compare training results</h1>
        <p className="text-sm text-muted-foreground">
          Select at least 2 results to compare from the{' '}
          <Link to="/results" className="underline underline-offset-2">
            training results list
          </Link>
          .
        </p>
      </div>
    )
  }

  const availableMetrics = availableComparisonMetricNames(comparisonMetrics)

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Compare training results</h1>
        <span className="flex-1" />
        <Button variant="ghost" size="icon" title="Refresh" onClick={refreshData}>
          <RefreshCw className="size-4" />
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Results being compared</Label>
          <MultiSelect
            options={allResults.map((r) => ({ value: String(r.id), label: `Result ${r.id} — ${r.model.name}` }))}
            value={ids.map(String)}
            onChange={updateCompareSelection}
            placeholder="Select results"
          />
        </div>
        <div className="space-y-1.5">
          <Label>Metrics</Label>
          <MultiSelect
            options={availableMetrics.map((m) => ({ value: m, label: m }))}
            value={selectedMetrics}
            onChange={setSelectedMetrics}
            placeholder="Select metrics"
          />
        </div>
      </div>

      {compared.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-card px-4 py-2.5 text-sm">
          {compared.map((r) => (
            <span key={r.id} className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full" style={{ backgroundColor: resultColors[r.id] }} />
              Result {r.id} — {r.model.name}
            </span>
          ))}
          <span className="text-muted-foreground">— solid = training, dashed = validation</span>
        </div>
      )}

      {selectedMetrics.length === 0 ? (
        <p className="text-sm text-muted-foreground">Select at least one metric to plot.</p>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {selectedMetrics.map((metricName) => {
            const chartShape = buildComparisonChartData(comparisonMetrics, metricName, resultColors)
            if (!chartShape) return null
            const chartData = toRechartsData(chartShape)
            const chartConfig: ChartConfig = Object.fromEntries(
              chartShape.datasets.map((d) => [
                d.label,
                { label: `${d.resultLabel} (${d.split === 'val' ? 'validation' : 'training'})`, color: d.borderColor },
              ]),
            )
            return (
              <Card key={metricName}>
                <CardHeader>
                  <CardTitle className="text-base">{metricName}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ChartContainer config={chartConfig} className="h-[300px] w-full">
                    <LineChart data={chartData}>
                      <CartesianGrid vertical={false} />
                      <XAxis dataKey="x" label={{ value: 'Epochs', position: 'insideBottom', offset: -5 }} />
                      <YAxis />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      {chartShape.datasets.map((d) => (
                        <Line
                          key={d.label}
                          type="monotone"
                          dataKey={d.label}
                          stroke={d.borderColor}
                          strokeDasharray={d.split === 'val' ? '5 5' : undefined}
                          dot={false}
                          strokeWidth={2}
                        />
                      ))}
                    </LineChart>
                  </ChartContainer>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Final metric values</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {compared.map((r) => (
            <Card key={r.id}>
              <CardHeader>
                <CardTitle className="text-base">
                  Result {r.id} — {r.model.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <MetricsTable rows={buildMetricsTable(r.train_metrics, r.val_metrics, r.test_metrics)} />
                {r.training_time != null && (
                  <p className="text-sm text-muted-foreground">
                    Training time: {r.training_time}
                    {typeof r.training_time === 'number' ? 's' : ''}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <Button variant="outline" onClick={() => downloadJSON(comparisonMetrics, 'comparison-metrics.json')}>
          <Download /> Download comparison data
        </Button>
      </div>
    </div>
  )
}
