<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import Dialog from 'primevue/dialog'
import { FilterMatchMode } from 'primevue/api'
import type { MenuItem } from 'primevue/menuitem'
import {
  getResults,
  getResultsOfDeployment,
  deleteResult,
  stopTraining,
  getTrainedModel,
  downloadBlob
} from '../api'
import { useNotify } from '../notify'
import { getLastMetric } from '../logic/format'
import type { TrainingResult, TrainingStatus } from '../types'

const route = useRoute()
const router = useRouter()
const notify = useNotify()
const confirm = useConfirm()

const deploymentID = route.params.id ? Number(route.params.id) : undefined
const results = ref<TrainingResult[]>([])
const filters = ref({ global: { value: null as string | null, matchMode: FilterMatchMode.CONTAINS } })

const statusIcons: Record<TrainingStatus, string> = {
  created: 'pi pi-pencil',
  deployed: 'pi pi-sign-in',
  stopped: 'pi pi-stop',
  finished: 'pi pi-check'
}

async function refreshData() {
  try {
    results.value =
      deploymentID !== undefined ? await getResultsOfDeployment(deploymentID) : await getResults()
  } catch {
    notify.error('Error connecting with the server')
  }
}

onMounted(refreshData)

const metricsDialogVisible = ref(false)
const metricsDialogData = ref<TrainingResult | null>(null)

function openMetricsDialog(result: TrainingResult) {
  metricsDialogData.value = result
  metricsDialogVisible.value = true
}

const menuRef = ref<InstanceType<typeof Menu> | null>(null)
const menuItems = ref<MenuItem[]>([])

function openMenu(event: Event, result: TrainingResult) {
  const items: MenuItem[] = [
    {
      label: 'Chart',
      icon: 'pi pi-chart-line',
      command: () => router.push(`/results/chart/${result.id}`)
    }
  ]
  if (result.status === 'finished') {
    items.push(
      {
        label: 'Inference',
        icon: 'pi pi-play',
        command: () => router.push(`/results/inference/${result.id}`)
      },
      {
        label: 'Deploy on IoT',
        icon: 'pi pi-wifi',
        command: () => router.push(`/results/inference-iot/${result.id}`)
      },
      { label: 'Download', icon: 'pi pi-download', command: () => downloadTrainedModel(result.id) }
    )
  }
  if (result.status !== 'deployed') {
    items.push({ label: 'Remove', icon: 'pi pi-trash', command: () => confirmDeletion(result.id) })
  } else {
    items.push({ label: 'Stop', icon: 'pi pi-stop', command: () => confirmStopping(result.id) })
  }
  menuItems.value = items
  menuRef.value?.toggle(event)
}

async function downloadTrainedModel(id: number) {
  try {
    const { blob, headers } = await getTrainedModel(id)
    const framework = headers.get('ML-Framework')
    const extension = framework === 'pth' ? '.pth' : '.h5'
    downloadBlob(blob, `model-result${id}${extension}`)
  } catch {
    notify.error('Error downloading the model')
  }
}

function confirmDeletion(id: number) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will remove Result ${id}`,
    accept: async () => {
      try {
        await deleteResult(id)
        results.value = results.value.filter((r) => r.id !== id)
        notify.ok('Result deleted')
      } catch (err) {
        notify.error('Error deleting the result: ' + (err as Error).message)
      }
    }
  })
}

function confirmStopping(id: number) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will stop Training result ${id} running from Kubernetes`,
    accept: async () => {
      try {
        await stopTraining(id)
        notify.ok('Training stopped')
        refreshData()
      } catch (err) {
        notify.error('Error stopping the training: ' + (err as Error).message)
      }
    }
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>
        Training results
        <span v-if="deploymentID !== undefined" class="subtitle"> of Deployment {{ deploymentID }}</span>
      </h1>
      <span class="spacer"></span>
      <Button icon="pi pi-refresh" text title="Refresh" @click="refreshData" />
    </div>

    <Menu ref="menuRef" :model="menuItems" popup />

    <Dialog v-model:visible="metricsDialogVisible" header="Metrics" modal style="min-width: 340px">
      <template v-if="metricsDialogData">
        <h4>Training metrics</h4>
        <pre>{{ getLastMetric(metricsDialogData.train_metrics) }}</pre>
        <h4>Validation metrics</h4>
        <pre>{{ getLastMetric(metricsDialogData.val_metrics) }}</pre>
        <h4>Test metrics</h4>
        <pre>{{ getLastMetric(metricsDialogData.test_metrics) }}</pre>
        <h4>Training time</h4>
        <div>{{ metricsDialogData.training_time }}</div>
      </template>
    </Dialog>

    <DataTable :value="results" v-model:filters="filters" paginator :rows="10" dataKey="id" class="surface">
      <template #header>
        <InputText v-model="filters.global.value" placeholder="Filter" />
      </template>
      <Column field="id" header="ID" sortable />
      <Column header="Model" sortable sortField="model.name">
        <template #body="{ data }">{{ data.model.name }}</template>
      </Column>
      <Column header="Metrics">
        <template #body="{ data }">
          <Button icon="pi pi-info-circle" text @click="openMetricsDialog(data)" />
        </template>
      </Column>
      <Column field="status" header="Status" sortable>
        <template #body="{ data }">
          <i :class="[statusIcons[data.status as TrainingStatus], `status-${data.status}`]" :title="data.status"></i>
        </template>
      </Column>
      <Column field="status_changed" header="Last status change" sortable />
      <Column header="Actions">
        <template #body="{ data }">
          <Button icon="pi pi-ellipsis-v" text @click="openMenu($event, data)" />
        </template>
      </Column>
    </DataTable>
  </div>
</template>
