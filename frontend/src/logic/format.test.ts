import { describe, it, expect } from 'vitest'
import { truncate, getLastMetric } from './format'

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
