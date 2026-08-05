// Turns the ngx-charts-shaped metrics payload from GET /results/chart/{id}
// (`[{name, series: [{name, value}]}]`) into a Chart.js dataset.
import type { ChartMetric, ChartDataShape, ChartDataset } from '../types'

export function availableMetricNames(metricsRetrieved: ChartMetric[]): string[] {
  return metricsRetrieved.map((m) => m.name).filter((name) => !name.endsWith('_val'))
}

// labels/datasets -> one recharts-ready row per epoch index, keyed by each
// dataset's own label. Promoted out of PlotView (was a private helper there)
// so ResultCompareView can reuse it too.
export function toRechartsData(shape: ChartDataShape): Record<string, string | number>[] {
  return shape.labels.map((label, i) => {
    const row: Record<string, string | number> = { x: label }
    for (const dataset of shape.datasets) row[dataset.label] = dataset.data[i]
    return row
  })
}

// A metric is shown if its name contains one of the selected base names, so
// selecting "loss" also plots "loss_val".
export function buildChartData(
  metricsRetrieved: ChartMetric[],
  selectedMetrics: string[],
  colors: string[]
): ChartDataShape | null {
  const shown = metricsRetrieved.filter((m) =>
    selectedMetrics.some((selected) => m.name.includes(selected))
  )
  if (shown.length === 0) return null

  const maxLen = Math.max(...shown.map((m) => m.series.length))
  return {
    labels: Array.from({ length: maxLen }, (_, i) => i),
    datasets: shown.map((m, i) => ({
      label: m.name,
      data: m.series.map((p) => p.value),
      borderColor: colors[i % colors.length],
      backgroundColor: colors[i % colors.length],
      fill: false,
      tension: 0.1
    }))
  }
}

// Results comparison view (ResultCompareView) - overlays several training
// results' metric curves, one facet per metric, one line per (result, split).

// Tied to the app's 5-slot theme-aware chart palette (--chart-1..--chart-5
// in index.css) rather than an arbitrary number - there's no 6th slot to
// assign a color from.
export const MAX_COMPARE_RESULTS = 5

// Parses the compare view's "ids" query param (comma-separated, possibly
// with whitespace/duplicates/garbage) into deduped positive integer ids,
// first-seen order preserved - that order drives color assignment, so it
// matters. Number('') is 0, not NaN, so `n > 0` does real work here, not
// just Number.isFinite.
export function parseCompareIds(raw: string | null): number[] {
  if (!raw) return []
  const seen = new Set<number>()
  const ids: number[] = []
  for (const part of raw.split(',')) {
    const n = Number(part.trim())
    if (Number.isInteger(n) && n > 0 && !seen.has(n)) {
      seen.add(n)
      ids.push(n)
    }
  }
  return ids
}

export interface ComparisonResultMetrics {
  resultId: number
  resultLabel: string
  metrics: ChartMetric[]
}

// Union of base metric names across every compared result ("_val"
// counterparts stay hidden, same rule as availableMetricNames). Sorted -
// unlike a single result's own metric list, there's no meaningful "original
// order" once several results' lists are merged.
export function availableComparisonMetricNames(results: ComparisonResultMetrics[]): string[] {
  const names = new Set<string>()
  for (const result of results) {
    for (const name of availableMetricNames(result.metrics)) names.add(name)
  }
  return Array.from(names).sort()
}

export interface ComparisonDataset extends ChartDataset {
  resultId: number
  resultLabel: string
  split: 'train' | 'val'
}

export interface ComparisonChartShape {
  labels: number[]
  datasets: ComparisonDataset[]
}

// Builds one facet's data for a single metric name across every compared
// result. Reuses buildChartData per result (identical base-name/"_val"
// matching) rather than reimplementing that logic - its own color output is
// discarded since color here is assigned by result, not by dataset index.
// A result missing this metric entirely is just absent from the facet, not
// padded with fabricated zeros. `labels` spans the longest of ALL results'
// own series for this metric, not just one - a shorter run's line simply
// stops (toRechartsData's indexed lookup yields undefined past its own
// dataset's length), which is the honest depiction, not a flat continuation.
export function buildComparisonChartData(
  results: ComparisonResultMetrics[],
  metricName: string,
  resultColors: Record<number, string>
): ComparisonChartShape | null {
  const perResult = results
    .map((result) => ({ result, shape: buildChartData(result.metrics, [metricName], ['#000']) }))
    .filter(
      (entry): entry is { result: ComparisonResultMetrics; shape: ChartDataShape } => entry.shape !== null
    )

  if (perResult.length === 0) return null

  const maxLen = Math.max(...perResult.map(({ shape }) => shape.labels.length))
  const color = (resultId: number) => resultColors[resultId] ?? '#888888'

  return {
    labels: Array.from({ length: maxLen }, (_, i) => i),
    datasets: perResult.flatMap(({ result, shape }) =>
      shape.datasets.map((d) => ({
        ...d,
        label: `R${result.resultId}: ${d.label}`,
        borderColor: color(result.resultId),
        backgroundColor: color(result.resultId),
        resultId: result.resultId,
        resultLabel: result.resultLabel,
        split: d.label.endsWith('_val') ? ('val' as const) : ('train' as const),
      })),
    ),
  }
}
