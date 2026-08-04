import { describe, it, expect } from 'vitest'
import { truncate, getLastMetric, formatDate } from './format'

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

describe('getLastMetric', () => {
  it('returns an empty string when metrics is null/undefined', () => {
    expect(getLastMetric(null)).toBe('')
    expect(getLastMetric(undefined)).toBe('')
  })

  it('formats the last value of each metric series', () => {
    const result = getLastMetric({ loss: [0.9, 0.5, 0.31234567], accuracy: [0.1, 0.6, 0.982] })
    expect(result).toBe('loss: 0.31235\naccuracy: 0.982')
  })

  it('rounds to 5 decimal places', () => {
    const result = getLastMetric({ loss: [0.123456789] })
    expect(result).toBe('loss: 0.12346')
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
