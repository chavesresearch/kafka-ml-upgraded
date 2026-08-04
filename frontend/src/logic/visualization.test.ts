import { describe, it, expect } from 'vitest'
import {
  INIT_COLOR,
  createClassificationState,
  applyClassificationMessage,
  classificationBarData,
  createRegressionState,
  applyRegressionMessage,
  regressionLineData,
  type VisualizationConfig
} from './visualization'

const classificationConfig: VisualizationConfig = {
  type: 'classification',
  average_updated: false,
  labels: [
    { id: 0, color: '#fff100', label: 'Zero' },
    { id: 1, color: '#ff8c00', label: 'One' }
  ]
}

describe('classification: immediate mode (average_updated=false)', () => {
  it('shows every incoming prediction as the current status', () => {
    const state = createClassificationState(classificationConfig)
    applyClassificationMessage(state, '1')
    expect(state.workingCondition).toBe('One')
    expect(state.currentColor).toBe('#ff8c00')
    expect(state.total).toBe(1)
  })

  it('rotates the last-status list, most recent first, capped at 4', () => {
    const state = createClassificationState(classificationConfig)
    ;['0', '1', '0', '1', '0'].forEach((id) => applyClassificationMessage(state, id))
    expect(state.lastStatuses).toHaveLength(4)
    expect(state.lastStatuses.map((s) => s.label)).toEqual(['One', 'Zero', 'One', 'Zero'])
  })

  it('tracks ids not present in the configured labels using a fallback color', () => {
    const state = createClassificationState(classificationConfig)
    applyClassificationMessage(state, '7')
    expect(state.labelDict[7]).toEqual({ color: INIT_COLOR, label: '7', value: 1 })
    expect(state.workingCondition).toBe('7')
  })

  it('builds bar chart data as a running average per label', () => {
    const state = createClassificationState(classificationConfig)
    applyClassificationMessage(state, '0')
    applyClassificationMessage(state, '0')
    applyClassificationMessage(state, '1')
    const bar = classificationBarData(state)
    expect(bar.labels).toEqual(['Zero', 'One'])
    expect(bar.datasets[0].data).toEqual([2 / 3, 1 / 3])
    expect(bar.datasets[0].backgroundColor).toEqual(['#fff100', '#ff8c00'])
  })

  it('bar chart data is all zeros before any message arrives', () => {
    const state = createClassificationState(classificationConfig)
    expect(classificationBarData(state).datasets[0].data).toEqual([0, 0])
  })
})

describe('classification: averaged mode (average_updated=true)', () => {
  const config: VisualizationConfig = { ...classificationConfig, average_updated: true, average_window: 3 }

  it('does not push a new "last status" entry while the leader is unchanged and no window boundary is hit', () => {
    const state = createClassificationState(config)
    applyClassificationMessage(state, '0') // leader becomes Zero; previous ('') is falsy, so nothing pushed
    expect(state.workingCondition).toBe('Zero')
    expect(state.lastStatuses).toHaveLength(0)
    applyClassificationMessage(state, '0') // leader still Zero (total=2, not a window boundary)
    expect(state.lastStatuses).toHaveLength(0)
  })

  it('refreshes on every average_window-th message even if the leader is unchanged', () => {
    const state = createClassificationState(config)
    applyClassificationMessage(state, '0')
    applyClassificationMessage(state, '0')
    const before = state.lastStatuses.length
    applyClassificationMessage(state, '0') // total=3 -> window boundary
    expect(state.lastStatuses.length).toBeGreaterThan(before)
  })

  it('does not divide by zero when average_window is 0/unset', () => {
    const state = createClassificationState({ ...classificationConfig, average_updated: true })
    expect(() => applyClassificationMessage(state, '0')).not.toThrow()
  })
})

describe('regression', () => {
  const regressionConfig: VisualizationConfig = {
    type: 'regression',
    labels: [
      { label: 'Temperature', color: '#0000FF' },
      { label: 'Humidity', color: '#33CCFF' }
    ]
  }

  it('accumulates one value per series per message, in order', () => {
    const state = createRegressionState(regressionConfig)
    applyRegressionMessage(state, JSON.stringify({ values: [21.5, 40] }))
    applyRegressionMessage(state, JSON.stringify({ values: [22.0, 41] }))
    expect(state.series[0].values).toEqual([21.5, 22.0])
    expect(state.series[1].values).toEqual([40, 41])
  })

  it('ignores extra values beyond the configured series', () => {
    const state = createRegressionState(regressionConfig)
    applyRegressionMessage(state, JSON.stringify({ values: [1, 2, 3, 4] }))
    expect(state.series).toHaveLength(2)
  })

  it('builds line chart data with one dataset per series and shared integer labels', () => {
    const state = createRegressionState(regressionConfig)
    applyRegressionMessage(state, JSON.stringify({ values: [1, 2] }))
    applyRegressionMessage(state, JSON.stringify({ values: [3, 4] }))
    const line = regressionLineData(state)
    expect(line.labels).toEqual([0, 1])
    expect(line.datasets).toHaveLength(2)
    expect(line.datasets[0]).toMatchObject({ label: 'Temperature', data: [1, 3], borderColor: '#0000FF' })
  })

  it('returns empty chart data before any message arrives', () => {
    const state = createRegressionState(regressionConfig)
    const line = regressionLineData(state)
    expect(line.labels).toEqual([])
    expect(line.datasets.every((d) => d.data.length === 0)).toBe(true)
  })
})
