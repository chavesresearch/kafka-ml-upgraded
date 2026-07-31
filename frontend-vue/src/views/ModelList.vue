<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { FilterMatchMode } from 'primevue/api'
import { getModels, deleteModel } from '../api'
import { useNotify } from '../notify'
import { truncate } from '../logic/format'
import type { MLModel } from '../types'

const notify = useNotify()
const confirm = useConfirm()

const models = ref<MLModel[]>([])
const filters = ref({ global: { value: null as string | null, matchMode: FilterMatchMode.CONTAINS } })

onMounted(async () => {
  try {
    models.value = await getModels()
  } catch {
    notify.error('Error connecting with the server')
  }
})

function confirmDelete(id: number) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will remove Model ${id}`,
    accept: async () => {
      try {
        await deleteModel(id)
        models.value = models.value.filter((m) => m.id !== id)
        notify.ok('Model deleted')
      } catch (err) {
        notify.error('Error deleting the model: ' + (err as Error).message)
      }
    }
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Models</h1>
      <span class="spacer"></span>
      <router-link to="/model-create">
        <Button icon="pi pi-plus" rounded title="Add a model" />
      </router-link>
    </div>

    <DataTable :value="models" v-model:filters="filters" paginator :rows="10" dataKey="id" class="surface">
      <template #header>
        <InputText v-model="filters.global.value" placeholder="Filter" />
      </template>
      <Column field="id" header="ID" sortable />
      <Column field="name" header="Name" sortable />
      <Column field="description" header="Description" />
      <Column header="Imports">
        <template #body="{ data }">
          <span :title="data.imports">{{ truncate(data.imports, 20) }}</span>
        </template>
      </Column>
      <Column header="Code">
        <template #body="{ data }">
          <span :title="data.code">{{ truncate(data.code, 20) }}</span>
        </template>
      </Column>
      <Column field="distributed" header="Distributed" />
      <Column header="Upper layer">
        <template #body="{ data }">{{ data.father ? data.father.name : '' }}</template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
          <router-link :to="`/model/${data.id}`">
            <Button icon="pi pi-eye" text title="View/edit model" />
          </router-link>
          <Button icon="pi pi-trash" text title="Delete model" @click="confirmDelete(data.id)" />
        </template>
      </Column>
    </DataTable>
  </div>
</template>
