import { describe, it, expect } from 'vitest'
import {
  availableMetricNames,
  buildChartData,
  toRechartsData,
  parseCompareIds,
  availableComparisonMetricNames,
  buildComparisonChartData,
  type ComparisonResultMetrics,
} from './plot'
import type { ChartMetric } from '../types'

const metrics: ChartMetric[] = [
  { name: 'loss', series: [{ name: '0', value: 0.9 }, { name: '1', value: 0.5 }] },
  { name: 'loss_val', series: [{ name: '0', value: 1.0 }, { name: '1', value: 0.7 }] },
  { name: 'accuracy', series: [{ name: '0', value: 0.5 }, { name: '1', value: 0.8 }, { name: '2', value: 0.9 }] }
]
const colors = ['#111111', '#222222', '#333333']

describe('availableMetricNames', () => {
  it('excludes "_val" suffixed metrics so only base names are offered', () => {
    expect(availableMetricNames(metrics)).toEqual(['loss', 'accuracy'])
  })

  it('returns an empty list for no metrics', () => {
    expect(availableMetricNames([])).toEqual([])
  })
})

describe('buildChartData', () => {
  it('returns null when nothing is selected', () => {
    expect(buildChartData(metrics, [], colors)).toBeNull()
  })

  it('selecting a base metric also plots its "_val" counterpart', () => {
    const data = buildChartData(metrics, ['loss'], colors)
    expect(data!.datasets.map((d) => d.label)).toEqual(['loss', 'loss_val'])
  })

  it('pads labels to the longest selected series', () => {
    const data = buildChartData(metrics, ['loss', 'accuracy'], colors)
    expect(data!.labels).toEqual([1, 2, 3]) // accuracy has 3 points, loss/loss_val have 2
  })

  it('assigns colors by dataset index, wrapping around the palette', () => {
    const data = buildChartData(metrics, ['loss', 'accuracy'], colors)
    expect(data!.datasets.map((d) => d.borderColor)).toEqual(['#111111', '#222222', '#333333'])
  })

  it('extracts only the value from each series point', () => {
    const data = buildChartData(metrics, ['accuracy'], colors)
    expect(data!.datasets[0].data).toEqual([0.5, 0.8, 0.9])
  })
})

describe('toRechartsData', () => {
  it('pivots labels/datasets into one row per epoch, keyed by dataset label', () => {
    const shape = buildChartData(metrics, ['loss'], colors)!
    expect(toRechartsData(shape)).toEqual([
      { x: 1, loss: 0.9, loss_val: 1.0 },
      { x: 2, loss: 0.5, loss_val: 0.7 },
    ])
  })

  it('a shorter dataset yields undefined past its own length, not a fabricated value', () => {
    const shape = buildChartData(metrics, ['loss', 'accuracy'], colors)!
    const rows = toRechartsData(shape)
    expect(rows[2]).toEqual({ x: 3, accuracy: 0.9, loss: undefined, loss_val: undefined })
  })
})

describe('parseCompareIds', () => {
  it('parses a comma-separated list, preserving first-seen order', () => {
    expect(parseCompareIds('3,1,2')).toEqual([3, 1, 2])
  })

  it('dedupes repeated ids, keeping the first occurrence', () => {
    expect(parseCompareIds('1,2,1,3,2')).toEqual([1, 2, 3])
  })

  it('drops non-numeric, zero, negative, and fractional entries', () => {
    expect(parseCompareIds('1,abc,0,-2,2.5,,4')).toEqual([1, 4])
  })

  it('returns an empty list for null or empty input', () => {
    expect(parseCompareIds(null)).toEqual([])
    expect(parseCompareIds('')).toEqual([])
  })

  it('tolerates surrounding whitespace', () => {
    expect(parseCompareIds(' 1 , 2 ,3 ')).toEqual([1, 2, 3])
  })
})

describe('availableComparisonMetricNames', () => {
  const resultA: ComparisonResultMetrics = { resultId: 1, resultLabel: 'Result 1', metrics }
  const resultB: ComparisonResultMetrics = {
    resultId: 2,
    resultLabel: 'Result 2',
    metrics: [{ name: 'accuracy', series: [{ name: '0', value: 0.4 }] }, { name: 'precision', series: [{ name: '0', value: 0.6 }] }],
  }

  it('unions base metric names across every result, sorted', () => {
    expect(availableComparisonMetricNames([resultA, resultB])).toEqual(['accuracy', 'loss', 'precision'])
  })

  it('returns an empty list when no results are given', () => {
    expect(availableComparisonMetricNames([])).toEqual([])
  })
})

describe('buildComparisonChartData', () => {
  const resultA: ComparisonResultMetrics = { resultId: 1, resultLabel: 'Result 1', metrics }
  const resultB: ComparisonResultMetrics = {
    resultId: 2,
    resultLabel: 'Result 2',
    metrics: [
      { name: 'loss', series: [{ name: '0', value: 0.6 }] },
      { name: 'loss_val', series: [{ name: '0', value: 0.65 }] },
    ],
  }
  const resultColors = { 1: 'var(--chart-1)', 2: 'var(--chart-2)' }

  it('namespaces each dataset label by result id so same-named metrics never collide', () => {
    const data = buildComparisonChartData([resultA, resultB], 'loss', resultColors)
    expect(data!.datasets.map((d) => d.label)).toEqual(['R1: loss', 'R1: loss_val', 'R2: loss', 'R2: loss_val'])
  })

  it('assigns color by result id, not by dataset index', () => {
    const data = buildComparisonChartData([resultA, resultB], 'loss', resultColors)
    expect(data!.datasets.map((d) => d.borderColor)).toEqual([
      'var(--chart-1)', 'var(--chart-1)', 'var(--chart-2)', 'var(--chart-2)',
    ])
  })

  it('marks the base name as the train split and the "_val" counterpart as val', () => {
    const data = buildComparisonChartData([resultA, resultB], 'loss', resultColors)
    expect(data!.datasets.map((d) => d.split)).toEqual(['train', 'val', 'train', 'val'])
  })

  it('labels span the longest of all results\' own series, not just one', () => {
    // resultA's loss has 2 points, resultB's has only 1.
    const data = buildComparisonChartData([resultA, resultB], 'loss', resultColors)
    expect(data!.labels).toEqual([1, 2])
  })

  it('a result missing the metric entirely is simply absent, not padded', () => {
    const noMetric: ComparisonResultMetrics = { resultId: 3, resultLabel: 'Result 3', metrics: [] }
    const data = buildComparisonChartData([resultA, noMetric], 'loss', resultColors)
    expect(data!.datasets.every((d) => d.resultId !== 3)).toBe(true)
  })

  it('returns null when no compared result has the metric', () => {
    const noMetric: ComparisonResultMetrics = { resultId: 3, resultLabel: 'Result 3', metrics: [] }
    expect(buildComparisonChartData([noMetric], 'loss', resultColors)).toBeNull()
  })
})
