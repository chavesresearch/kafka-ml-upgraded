<script setup lang="ts">
import { ref, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { FilterMatchMode } from 'primevue/api'
import { getDatasources, deployDatasource } from '../api'
import { useNotify } from '../notify'
import { truncate } from '../logic/format'
import type { Datasource } from '../types'

const notify = useNotify()

const datasources = ref<Datasource[]>([])
const filters = ref({ global: { value: null as string | null, matchMode: FilterMatchMode.CONTAINS } })

onMounted(async () => {
  try {
    datasources.value = await getDatasources()
  } catch {
    notify.error('Error connecting with the server')
  }
})

const dialogVisible = ref(false)
const selectedDatasource = ref<Datasource | null>(null)
const targetDeployment = ref<number | null>(null)

function openSendDialog(datasource: Datasource) {
  selectedDatasource.value = datasource
  targetDeployment.value = null
  dialogVisible.value = true
}

async function send() {
  if (!selectedDatasource.value) return
  const data = { ...selectedDatasource.value, deployment: String(targetDeployment.value) }
  dialogVisible.value = false
  try {
    await deployDatasource(data)
    notify.ok('Datasource sent to Kafka. Refresh the page in a while to see it')
  } catch (err) {
    notify.error('Error sending the datasource: ' + (err as Error).message)
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Datasources received</h1>
    </div>

    <Dialog
      v-model:visible="dialogVisible"
      header="Send datasource to deployment"
      modal
      style="max-width: 420px"
    >
      <p>
        Please, make sure that the timestamp of the datasource is less than
        KAFKA_LOG_RETENTION_DAYS. Otherwise, the datasource could have been deleted from Kafka.
      </p>
      <div class="field">
        <label>Deployment ID *</label>
        <InputNumber v-model="targetDeployment" :useGrouping="false" />
      </div>
      <template #footer>
        <Button label="Cancel" text @click="dialogVisible = false" />
        <Button label="Send" :disabled="targetDeployment == null" @click="send" />
      </template>
    </Dialog>

    <DataTable :value="datasources" v-model:filters="filters" paginator :rows="10" class="surface">
      <template #header>
        <InputText v-model="filters.global.value" placeholder="Filter" />
      </template>
      <Column field="description" header="Description" />
      <Column field="deployment" header="Deployment" sortable />
      <Column field="input_format" header="Input format" />
      <Column header="Input configuration">
        <template #body="{ data }">
          <span :title="data.input_config">{{ truncate(data.input_config, 10) }}</span>
        </template>
      </Column>
      <Column field="topic" header="Kafka topic" />
      <Column field="validation_rate" header="Validation rate" />
      <Column field="test_rate" header="Test rate" />
      <Column field="total_msg" header="Total msg" />
      <Column field="time" header="Time" sortable />
      <Column header="Send again">
        <template #body="{ data }">
          <Button
            icon="pi pi-sign-in"
            text
            title="Send again to another deployment"
            @click="openSendDialog(data)"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>
