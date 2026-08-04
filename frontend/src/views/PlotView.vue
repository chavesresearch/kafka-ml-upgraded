<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import MultiSelect from 'primevue/multiselect'
import Button from 'primevue/button'
import Chart from 'primevue/chart'
import { getChartInfo, getConfusionMatrix, downloadJSON } from '../api'
import { useNotify } from '../notify'
import { availableMetricNames, buildChartData } from '../logic/plot'
import type { ChartMetric } from '../types'

// Same palette as the Angular plot view.
const COLORS = [
  '#FF3333', '#FF33FF', '#CC33FF', '#0000FF', '#33CCFF',
  '#33FFFF', '#33FF66', '#CCFF33', '#FFCC00', '#FF6600'
]

const route = useRoute()
const notify = useNotify()

const resultID = Number(route.params.id)
const metricsRetrieved = ref<ChartMetric[]>([])
const confMatrixRetrieved = ref<unknown>(null)
const availableMetrics = ref<string[]>([])
const selectedMetrics = ref<string[]>([])
const confusionMatrixUrl = ref<string | null>(null)

async function refreshData() {
  try {
    const data = await getChartInfo(resultID)
    metricsRetrieved.value = data.metrics || []
    // Offer only base metric names; picking one also plots its "<name>_val" series.
    availableMetrics.value = availableMetricNames(metricsRetrieved.value)
    confMatrixRetrieved.value = data.conf_mat

    if (data.conf_mat != null) {
      const { blob } = await getConfusionMatrix(resultID)
      confusionMatrixUrl.value = URL.createObjectURL(blob)
    }
  } catch {
    notify.error('The training result does not exist')
  }
}

onMounted(refreshData)

const chartData = computed(() =>
  buildChartData(metricsRetrieved.value, selectedMetrics.value, COLORS)
)

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: { x: { title: { display: true, text: 'Epochs' } } }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Training result {{ resultID }} Metrics charts</h1>
      <span class="spacer"></span>
      <Button icon="pi pi-refresh" text title="Refresh" @click="refreshData" />
    </div>

    <div class="field" style="max-width: 420px">
      <label>Select Metrics</label>
      <MultiSelect
        v-model="selectedMetrics"
        :options="availableMetrics"
        placeholder="Select metrics"
        display="chip"
      />
    </div>

    <div v-if="chartData" class="surface" style="height: 400px; padding: 1.25rem">
      <Chart type="line" :data="chartData" :options="chartOptions" style="height: 100%" />
    </div>

    <div class="row-buttons" style="justify-content: flex-start">
      <Button
        label="Download Metrics in JSON Format"
        icon="pi pi-download"
        outlined
        @click="downloadJSON(metricsRetrieved, 'metrics.json')"
      />
    </div>

    <div v-if="confMatrixRetrieved != null">
      <img
        v-if="confusionMatrixUrl"
        :src="confusionMatrixUrl"
        alt="Confusion Matrix Image"
        style="max-width: 100%; border-radius: var(--radius-md)"
      />
      <div class="row-buttons" style="justify-content: flex-start">
        <Button
          label="Download Confusion Matrix in JSON Format"
          icon="pi pi-download"
          outlined
          @click="downloadJSON(confMatrixRetrieved, 'conf_matrix.json')"
        />
      </div>
    </div>
  </div>
</template>
