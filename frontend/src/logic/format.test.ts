import { describe, it, expect } from 'vitest'
import { truncate, buildMetricsTable, formatDate } from './format'

describe('truncate', () => {
  it('returns an empty string for falsy input', () => {
    expect(truncate('', 10)).toBe('')
    expect(truncate(null, 10)).toBe('')
    expect(truncate(undefined, 10)).toBe('')
  })

  it('leaves short strings untouched (no ellipsis)', () => {
    expect(truncate('short', 20)).toBe('short')
  })

  it('cuts long strings and appends " ..."', () => {
    expect(truncate('this is a long string', 4)).toBe('this ...')
  })
})

describe('buildMetricsTable', () => {
  it('returns an empty array when all three dicts are null/undefined', () => {
    expect(buildMetricsTable(null, null, null)).toEqual([])
    expect(buildMetricsTable(undefined, undefined, undefined)).toEqual([])
  })

  it('merges same-named metrics from all three splits into one row each, sorted by name', () => {
    const rows = buildMetricsTable(
      { accuracy: [0.5357142686843872], loss: [0.7193791270256042] },
      { accuracy: [0.375], loss: [0.7342627048492432] },
      { accuracy: [0.728183925151825], loss: [0.5] }
    )
    expect(rows).toEqual([
      { name: 'accuracy', train: 0.53571, val: 0.375, test: 0.72818 },
      { name: 'loss', train: 0.71938, val: 0.73426, test: 0.5 },
    ])
  })

  it('uses the last value of a multi-epoch series', () => {
    const rows = buildMetricsTable({ loss: [0.9, 0.5, 0.31234567] }, null, null)
    expect(rows).toEqual([{ name: 'loss', train: 0.31235, val: undefined, test: undefined }])
  })

  it('rounds to 5 decimal places', () => {
    const rows = buildMetricsTable({ loss: [0.123456789] }, null, null)
    expect(rows[0].train).toBe(0.12346)
  })

  it('leaves a metric missing from a split as undefined, not 0 or NaN', () => {
    // e.g. no test set was configured for this deployment.
    const rows = buildMetricsTable({ loss: [0.1] }, { loss: [0.2] }, {})
    expect(rows).toEqual([{ name: 'loss', train: 0.1, val: 0.2, test: undefined }])
  })

  it('includes a metric name that only appears in one split', () => {
    const rows = buildMetricsTable({ loss: [0.1], custom_metric: [42] }, { loss: [0.2] }, null)
    expect(rows).toEqual([
      { name: 'custom_metric', train: 42, val: undefined, test: undefined },
      { name: 'loss', train: 0.1, val: 0.2, test: undefined },
    ])
  })
})

describe('formatDate', () => {
  it('returns an empty string for falsy input', () => {
    expect(formatDate('')).toBe('')
    expect(formatDate(null)).toBe('')
    expect(formatDate(undefined)).toBe('')
  })

  it('treats a naive backend timestamp as UTC, not local time', () => {
    // 1970-01-01T00:00:00 UTC, with microsecond precision like the
    // backend actually sends - must format identically to the same
    // instant with an explicit Z suffix.
    expect(formatDate('1970-01-01T00:00:00.000000')).toBe(formatDate('1970-01-01T00:00:00.000000Z'))
  })

  it('does not double-apply a timezone when an offset is already present', () => {
    const withZ = formatDate('2026-08-04T14:21:39.255981Z')
    const withOffset = formatDate('2026-08-04T14:21:39.255981+00:00')
    expect(withZ).toBe(withOffset)
  })

  it('falls back to the raw string for unparseable input', () => {
    expect(formatDate('not a date')).toBe('not a date')
  })

  it('produces a human-readable, non-raw-ISO string', () => {
    const result = formatDate('2026-08-04T14:21:39.255981')
    expect(result).not.toContain('T')
    expect(result).not.toContain('2026-08-04T')
  })
})
