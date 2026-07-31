<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Chart from 'primevue/chart'
import CodeEditor from '../components/CodeEditor.vue'
import { createVisualizationSocket, type VisualizationSocket } from '../ws'
import { useNotify } from '../notify'
import {
  INIT_COLOR,
  createClassificationState,
  applyClassificationMessage,
  classificationBarData,
  createRegressionState,
  applyRegressionMessage,
  regressionLineData,
  type ClassificationState,
  type RegressionState,
  type VisualizationConfig
} from '../logic/visualization'
import type { ChartDataShape } from '../types'

const notify = useNotify()

const config = ref('')
const topic = ref('')
const isClassification = ref(false)
const isRegression = ref(false)
const connected = ref(false)
const topicConfigured = ref(false)

// Template-facing view of the classification/regression state machines
// (see src/logic/visualization.ts). The state machines themselves are kept
// as plain objects outside Vue's reactivity; only their rendered output is
// pushed into refs after each update.
const workingCondition = ref('')
const currentColor = ref(INIT_COLOR)
const lastStatuses = ref<{ label: string; color: string }[]>([])
const barData = ref<ChartDataShape | null>(null)
const lineData = ref<ChartDataShape | null>(null)

let classificationState: ClassificationState | null = null
let regressionState: RegressionState | null = null
let socket: VisualizationSocket | null = null

function setConfig() {
  try {
    const parsed = JSON.parse(config.value) as VisualizationConfig
    closeWS()
    isClassification.value = false
    isRegression.value = false
    if (parsed.type === 'classification') {
      classificationState = createClassificationState(parsed)
      syncClassificationView()
      isClassification.value = true
    } else if (parsed.type === 'regression') {
      regressionState = createRegressionState(parsed)
      lineData.value = regressionLineData(regressionState)
      isRegression.value = true
    } else {
      throw new Error('Type not recognized, available types: classification and regression')
    }
    notify.ok('Configuration set correctly')
  } catch (e) {
    notify.error(`Configuration not valid: [${e}]`)
  }
}

function syncClassificationView() {
  if (!classificationState) return
  workingCondition.value = classificationState.workingCondition
  currentColor.value = classificationState.currentColor
  lastStatuses.value = classificationState.lastStatuses
  barData.value = classificationBarData(classificationState)
}

function onClassificationData(data: string) {
  if (!classificationState) return
  applyClassificationMessage(classificationState, data)
  syncClassificationView()
}

function onRegressionData(data: string) {
  if (!regressionState) return
  applyRegressionMessage(regressionState, data)
  lineData.value = regressionLineData(regressionState)
}

/* WebSocket */
function sendTopic() {
  if (!connected.value) {
    socket = createVisualizationSocket({
      onMessage: (data) => {
        if (isClassification.value) onClassificationData(data)
        else if (isRegression.value) onRegressionData(data)
      },
      onError: () => {
        notify.error('Error connecting with the server')
        connected.value = false
      },
      onClose: () => {
        connected.value = false
        topicConfigured.value = false
      }
    })
    connected.value = true
  }
  // Give the socket a moment to open before subscribing (as the Angular app did).
  setTimeout(() => {
    if (socket && socket.sendTopic(topic.value, isClassification.value)) {
      notify.ok('Connected to topic: ' + topic.value)
      topicConfigured.value = true
    } else {
      notify.error('Error sending the message')
    }
  }, 1000)
}

function closeWS() {
  if (connected.value && socket) {
    socket.close()
    socket = null
    connected.value = false
    topicConfigured.value = false
  }
}

onUnmounted(closeWS)

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  scales: { y: { min: 0, max: 1 } },
  plugins: { legend: { display: false } }
}

const lineOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false
}
</script>

<template>
  <div class="page">
    <div class="field" style="max-width: 640px">
      <label>Label config</label>
      <CodeEditor
        v-model="config"
        language="plaintext"
        height="140px"
        placeholder='{&#10;  "type": "classification",&#10;  "labels": [...]&#10;}'
      />
      <div class="row-buttons" style="justify-content: flex-start; border-top: none; padding-top: 0.5rem">
        <Button icon="pi pi-tag" label="Set configuration" outlined @click="setConfig" />
      </div>
    </div>

    <div class="field" style="max-width: 640px" v-if="isClassification || isRegression">
      <label>Kafka output topic</label>
      <div style="display: flex; gap: 0.5rem">
        <InputText v-model="topic" class="full-width" :disabled="connected || topicConfigured" />
        <Button
          icon="pi pi-send"
          outlined
          title="Connect to topic"
          :disabled="connected || topicConfigured"
          @click="sendTopic"
        />
        <Button v-if="connected" icon="pi pi-times" outlined title="Disconnect" @click="closeWS" />
      </div>
    </div>

    <template v-if="isClassification">
      <h2>Current status</h2>
      <div class="status-box" :style="{ backgroundColor: currentColor }">
        <p>{{ workingCondition }}</p>
      </div>

      <h2>Last status</h2>
      <div class="last-status-row">
        <div
          v-for="(status, i) in lastStatuses"
          :key="i"
          class="last-status-cell"
          :style="{ backgroundColor: status.color }"
        >
          {{ status.label }}
        </div>
      </div>

      <h2>Average</h2>
      <div class="surface" style="height: 320px; padding: 1.25rem" v-if="barData">
        <Chart type="bar" :data="barData" :options="barOptions" style="height: 100%" />
      </div>
    </template>

    <div v-if="isRegression" class="surface" style="height: 400px; margin-top: 1rem; padding: 1.25rem">
      <Chart v-if="lineData" type="line" :data="lineData" :options="lineOptions" style="height: 100%" />
    </div>
  </div>
</template>

<style scoped>
h2 {
  margin: 1.2rem 0 0.6rem;
  font-weight: 600;
  font-size: 1rem;
}

.status-box {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.status-box p {
  font-size: 2rem;
  font-weight: 650;
}

.last-status-row {
  display: flex;
  gap: 0.5rem;
}

.last-status-cell {
  flex: 1;
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  font-weight: 600;
}
</style>
