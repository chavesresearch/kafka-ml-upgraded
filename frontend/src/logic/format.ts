// Small display-formatting helpers shared by list/detail views.

export function truncate(text: string | null | undefined, n: number): string {
  if (!text) return ''
  return text.slice(0, n) + (text.length > n ? ' ...' : '')
}

// Backend timestamps (TrainingResult.status_changed, Deployment.time, etc.)
// are UTC but serialized without a timezone suffix - SQLite doesn't
// preserve tzinfo across storage/retrieval even though the column is
// declared DateTime(timezone=True) (confirmed empirically: a real
// timestamp compared against `date -u` at the same moment matched UTC,
// not local time - not assumed from the column declaration alone). Treat
// as UTC by appending "Z" before parsing, unless an offset is already
// present, then render in the browser's own locale/timezone.
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const hasOffset = /[Zz]|[+-]\d\d:\d\d$/.test(iso)
  const date = new Date(hasOffset ? iso : `${iso}Z`)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    date
  )
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
