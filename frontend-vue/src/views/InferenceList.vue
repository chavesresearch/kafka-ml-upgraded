<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { FilterMatchMode } from 'primevue/api'
import { getInferences, stopInference, deleteInference } from '../api'
import { useNotify } from '../notify'
import { truncate } from '../logic/format'
import type { Inference } from '../types'

const notify = useNotify()
const confirm = useConfirm()

const inferences = ref<Inference[]>([])
const filters = ref({ global: { value: null as string | null, matchMode: FilterMatchMode.CONTAINS } })

async function refreshData() {
  try {
    inferences.value = await getInferences()
  } catch {
    notify.error('Error connecting with the server')
  }
}

onMounted(refreshData)

function confirmStopping(id: number) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will stop Inference ${id} running from Kubernetes`,
    accept: async () => {
      try {
        await stopInference(id)
        notify.ok('Inference stopped')
        refreshData()
      } catch (err) {
        notify.error('Error stopping the inference: ' + (err as Error).message)
      }
    }
  })
}

function confirmDeletion(id: number) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will remove Inference ${id}`,
    accept: async () => {
      try {
        await deleteInference(id)
        inferences.value = inferences.value.filter((i) => i.id !== id)
        notify.ok('Inference deleted')
      } catch (err) {
        notify.error('Error deleting the inference: ' + (err as Error).message)
      }
    }
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Inference</h1>
    </div>

    <DataTable :value="inferences" v-model:filters="filters" paginator :rows="10" dataKey="id" class="surface">
      <template #header>
        <InputText v-model="filters.global.value" placeholder="Filter" />
      </template>
      <Column field="id" header="ID" sortable />
      <Column field="model_result" header="Training ID" sortable />
      <Column field="replicas" header="Replicas" />
      <Column field="input_format" header="Input format" />
      <Column header="Input configuration">
        <template #body="{ data }">
          <span :title="data.input_config">{{ truncate(data.input_config, 10) }}</span>
        </template>
      </Column>
      <Column field="external_host" header="Host" />
      <Column field="input_topic" header="Kafka input topic" />
      <Column field="output_topic" header="Kafka output topic" />
      <Column field="output_upper" header="Kafka output to upper model" />
      <Column field="limit" header="Prediction limit" />
      <Column field="time" header="Time" sortable />
      <Column field="status" header="Status">
        <template #body="{ data }">
          <i v-if="data.status === 'stopped'" class="pi pi-stop status-stopped" title="stopped"></i>
          <i v-if="data.status === 'deployed'" class="pi pi-check status-deployed" title="deployed"></i>
        </template>
      </Column>
      <Column header="Manage">
        <template #body="{ data }">
          <Button
            v-if="data.status === 'stopped'"
            icon="pi pi-trash"
            text
            title="Remove inference"
            @click="confirmDeletion(data.id)"
          />
          <Button
            v-if="data.status === 'deployed'"
            icon="pi pi-stop"
            text
            title="Stop inference"
            @click="confirmStopping(data.id)"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>
