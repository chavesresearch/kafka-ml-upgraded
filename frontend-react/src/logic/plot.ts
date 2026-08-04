// Turns the ngx-charts-shaped metrics payload from GET /results/chart/{id}
// (`[{name, series: [{name, value}]}]`) into a Chart.js dataset.
import type { ChartMetric, ChartDataShape } from '../types'

export function availableMetricNames(metricsRetrieved: ChartMetric[]): string[] {
  return metricsRetrieved.map((m) => m.name).filter((name) => !name.endsWith('_val'))
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
