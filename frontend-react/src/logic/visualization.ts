// Pure state machine for the live Visualization view: turns incoming
// WebSocket messages into the label/chart state the template renders.
// Kept framework-free so it can be unit tested without mounting a component
// or opening a real WebSocket.
import type { ChartDataShape } from '../types'

export const INIT_COLOR = '#D3D3D3'

export interface VisualizationLabel {
  id?: number
  color: string
  label: string
}

export interface VisualizationConfig {
  type: 'classification' | 'regression'
  average_updated?: boolean
  average_window?: number
  labels: VisualizationLabel[]
}

interface LabelEntry {
  color: string
  label: string
  value: number
}

export interface ClassificationState {
  labelDict: Record<string | number, LabelEntry>
  total: number
  averageUpdated: boolean
  averageWindow: number
  workingCondition: string
  currentColor: string
  lastStatuses: { label: string; color: string }[] // most recent first, capped to 4
}

export function createClassificationState(parsed: VisualizationConfig): ClassificationState {
  const labelDict: Record<string | number, LabelEntry> = {}
  for (const entry of parsed.labels) {
    labelDict[entry.id ?? entry.label] = { color: entry.color, label: entry.label, value: 0 }
  }
  return {
    labelDict,
    total: 0,
    averageUpdated: Boolean(parsed.average_updated),
    averageWindow: parsed.average_window || 0,
    workingCondition: '',
    currentColor: INIT_COLOR,
    lastStatuses: []
  }
}

function pushLastStatus(state: ClassificationState, label: string, color: string): void {
  if (!label) return
  state.lastStatuses = [{ label, color }, ...state.lastStatuses].slice(0, 4)
}

// Mutates state in place to reflect one incoming classification id, and
// returns it for convenient chaining/assignment.
export function applyClassificationMessage(
  state: ClassificationState,
  data: string
): ClassificationState {
  const id = parseInt(data, 10)
  if (state.labelDict[id]) {
    state.labelDict[id].value += 1
  } else {
    // Id not present in the configured labels: track it anyway so counts stay correct.
    state.labelDict[id] = { color: INIT_COLOR, label: String(id), value: 1 }
  }
  state.total += 1

  if (!state.averageUpdated) {
    // Show every prediction as it arrives.
    pushLastStatus(state, state.workingCondition, state.currentColor)
    state.workingCondition = state.labelDict[id].label
    state.currentColor = state.labelDict[id].color
  } else {
    // Show the label with the highest running average, refreshed only when
    // it changes or every `averageWindow` messages.
    let best: LabelEntry | null = null
    for (const key of Object.keys(state.labelDict)) {
      const entry = state.labelDict[key]
      if (!best || entry.value > best.value) best = entry
    }
    if (
      best &&
      (best.label !== state.workingCondition ||
        (state.averageWindow > 0 && state.total % state.averageWindow === 0))
    ) {
      pushLastStatus(state, state.workingCondition, state.currentColor)
      state.workingCondition = best.label
      state.currentColor = best.color
    }
  }
  return state
}

export function classificationBarData(state: ClassificationState): ChartDataShape {
  const ids = Object.keys(state.labelDict)
  return {
    labels: ids.map((id) => state.labelDict[id].label),
    datasets: [
      {
        label: 'Average',
        data: ids.map((id) => (state.total ? state.labelDict[id].value / state.total : 0)),
        backgroundColor: ids.map((id) => state.labelDict[id].color)
      }
    ]
  }
}

export interface RegressionState {
  series: { label: string; color: string; values: number[] }[]
}

export function createRegressionState(parsed: VisualizationConfig): RegressionState {
  return {
    series: parsed.labels.map((entry) => ({ label: entry.label, color: entry.color, values: [] }))
  }
}

// Message shape: {"values": [v0, v1, ...]}, one value per configured series, in order.
export function applyRegressionMessage(state: RegressionState, data: string): RegressionState {
  const parsed = JSON.parse(data) as { values: number[] }
  parsed.values.forEach((value, i) => {
    if (state.series[i]) state.series[i].values.push(value)
  })
  return state
}

export function regressionLineData(state: RegressionState): ChartDataShape {
  const maxLen = Math.max(0, ...state.series.map((s) => s.values.length))
  return {
    labels: Array.from({ length: maxLen }, (_, i) => i),
    datasets: state.series.map((s) => ({
      label: s.label,
      data: [...s.values],
      borderColor: s.color,
      backgroundColor: s.color,
      fill: false,
      pointRadius: 0
    }))
  }
}
