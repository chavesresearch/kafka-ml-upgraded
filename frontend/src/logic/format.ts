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

function lastValue(series: number[] | undefined): number | undefined {
  if (!series || series.length === 0) return undefined
  return Math.round((series[series.length - 1] + Number.EPSILON) * 100000) / 100000
}

export interface MetricsTableRow {
  name: string
  train: number | undefined
  val: number | undefined
  test: number | undefined
}

// Merges a TrainingResult's three independent metric dicts (train/val/test,
// each {metricName: [values...]} with the *same* plain metric names -
// confirmed against a real result: train_metrics/val_metrics/test_metrics
// all key off "accuracy"/"loss", no "val_"/"test_" prefix within each dict,
// unlike the chart endpoint's combined series) into one row per metric
// name, last value of each series, for a side-by-side table instead of
// three separate text dumps. A metric missing from a given split (e.g. no
// test set configured) comes back as `undefined` for that column - the
// caller renders that as an em dash, not "undefined" or a blank cell that
// could be mistaken for a real 0.
export function buildMetricsTable(
  train: Record<string, number[]> | null | undefined,
  val: Record<string, number[]> | null | undefined,
  test: Record<string, number[]> | null | undefined
): MetricsTableRow[] {
  const names = new Set([
    ...Object.keys(train ?? {}),
    ...Object.keys(val ?? {}),
    ...Object.keys(test ?? {}),
  ])
  return Array.from(names)
    .sort()
    .map((name) => ({
      name,
      train: lastValue(train?.[name]),
      val: lastValue(val?.[name]),
      test: lastValue(test?.[name]),
    }))
}
