// Small display-formatting helpers shared by list/detail views.

export function truncate(text: string | null | undefined, n: number): string {
  if (!text) return ''
  return text.slice(0, n) + (text.length > n ? ' ...' : '')
}

// Renders the last value of each metric series, e.g. "loss: 0.123\naccuracy: 0.98".
// metrics is a dict of {metricName: [values...]}, as stored on a TrainingResult.
export function getLastMetric(metrics: Record<string, number[]> | null | undefined): string {
  if (!metrics) return ''
  return Object.keys(metrics)
    .map((name) => {
      const series = metrics[name]
      const value = Math.round((series[series.length - 1] + Number.EPSILON) * 100000) / 100000
      return `${name}: ${value}`
    })
    .join('\n')
}
