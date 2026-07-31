<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { FilterMatchMode } from 'primevue/api'
import { getIoTDevices, deleteIoTDevice } from '../api'
import { useNotify } from '../notify'
import type { IoTDevice } from '../types'

const notify = useNotify()
const confirm = useConfirm()

const devices = ref<IoTDevice[]>([])
const filters = ref({ global: { value: null as string | null, matchMode: FilterMatchMode.CONTAINS } })

onMounted(async () => {
  try {
    devices.value = await getIoTDevices()
  } catch {
    notify.error('Error connecting with the server')
  }
})

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    notify.ok('Copied to clipboard')
  } catch (err) {
    notify.error('Error copying to clipboard: ' + err)
  }
}

function confirmDelete(id: number, token: string) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will remove Device ${token}`,
    accept: async () => {
      try {
        await deleteIoTDevice(id)
        devices.value = devices.value.filter((d) => d.id !== id)
        notify.ok('Device deleted')
      } catch (err) {
        notify.error('Error deleting the device: ' + (err as Error).message)
      }
    }
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Tasmota ML-Enabled IoT Devices</h1>
      <span class="spacer"></span>
      <router-link to="/devices-create">
        <Button icon="pi pi-plus" rounded title="Add a new device" />
      </router-link>
    </div>

    <DataTable :value="devices" v-model:filters="filters" paginator :rows="10" dataKey="id" class="surface">
      <template #header>
        <InputText v-model="filters.global.value" placeholder="Filter" />
      </template>
      <Column field="token" header="MQTT ID" sortable />
      <Column field="friendly_name" header="Friendly Name" sortable />
      <Column header="MQTT Broker">
        <template #body="{ data }">{{ data.mqtt_address }}:{{ data.mqtt_port }}</template>
      </Column>
      <Column header="Configuration">
        <template #body="{ data }">
          <Button
            icon="pi pi-copy"
            text
            title="Copy configuration"
            @click="copyToClipboard(data.backlog)"
          />
        </template>
      </Column>
      <Column field="status" header="Status">
        <template #body="{ data }">
          <i
            v-if="data.status === 'connected'"
            class="pi pi-cloud-upload status-connected"
            title="connected"
          ></i>
          <i
            v-if="data.status === 'disconnected'"
            class="pi pi-cloud-download status-disconnected"
            title="disconnected"
          ></i>
        </template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
          <router-link :to="`/device/${data.id}`">
            <Button icon="pi pi-pencil" text title="View/edit device" />
          </router-link>
          <Button
            icon="pi pi-trash"
            text
            title="Delete device"
            @click="confirmDelete(data.id, data.token)"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>
