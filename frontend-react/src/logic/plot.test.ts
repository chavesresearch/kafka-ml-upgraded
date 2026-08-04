import { describe, it, expect } from 'vitest'
import { availableMetricNames, buildChartData } from './plot'
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
    expect(data!.labels).toEqual([0, 1, 2]) // accuracy has 3 points, loss/loss_val have 2
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
