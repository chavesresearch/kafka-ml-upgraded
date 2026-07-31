<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import { getConfigurations, deleteConfiguration } from '../api'
import { useNotify } from '../notify'
import type { Configuration } from '../types'

const notify = useNotify()
const confirm = useConfirm()
const router = useRouter()

const configurations = ref<Configuration[]>([])
const filter = ref('')

onMounted(async () => {
  try {
    configurations.value = await getConfigurations()
  } catch {
    notify.error('Error connecting with the server')
  }
})

// Same behavior as the Angular datafilter pipe: match any field, case-insensitive.
const filtered = computed(() => {
  const text = filter.value.trim().toLowerCase()
  if (!text) return configurations.value
  return configurations.value.filter((c) =>
    Object.values(c).some((v) => String(v).toLowerCase().includes(text))
  )
})

const menuRef = ref<InstanceType<typeof Menu> | null>(null)
const menuItems = ref<MenuItem[]>([])

function openMenu(event: Event, configuration: Configuration) {
  menuItems.value = [
    { label: 'View', icon: 'pi pi-eye', command: () => router.push(`/configuration/${configuration.id}`) },
    { label: 'Deploy', icon: 'pi pi-play', command: () => router.push(`/deploy/${configuration.id}`) },
    {
      label: 'Deployments',
      icon: 'pi pi-external-link',
      command: () => router.push(`/deployments/${configuration.id}`)
    },
    { label: 'Remove', icon: 'pi pi-trash', command: () => confirmDelete(configuration.id) }
  ]
  menuRef.value?.toggle(event)
}

function confirmDelete(id: number) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will remove Configuration ${id}`,
    accept: async () => {
      try {
        await deleteConfiguration(id)
        configurations.value = configurations.value.filter((c) => c.id !== id)
        notify.ok('Configuration deleted')
      } catch (err) {
        notify.error('Error deleting the configuration: ' + (err as Error).message)
      }
    }
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>Configurations</h1>
      <span class="spacer"></span>
      <router-link to="/configuration-create">
        <Button icon="pi pi-plus" rounded title="Add a configuration" />
      </router-link>
    </div>

    <div class="field">
      <InputText v-model="filter" placeholder="Filter" />
    </div>

    <Menu ref="menuRef" :model="menuItems" popup />

    <div class="card-grid">
      <Card v-for="configuration in filtered" :key="configuration.id" class="dashboard-card surface">
        <template #title>
          <div class="card-title-row">
            <div class="title">
              <h3>{{ configuration.name }}</h3>
              <h6>{{ configuration.description }}</h6>
            </div>
            <Button icon="pi pi-ellipsis-v" text @click="openMenu($event, configuration)" />
          </div>
        </template>
        <template #content>
          <h3>ML Models:</h3>
          <div v-for="model in configuration.ml_models" :key="model.id">
            <router-link :to="`/model/${model.id}`">
              <Button :label="model.name" size="small" outlined :title="`View/Edit Model ${model.id}`" />
            </router-link>
          </div>
          <h3>Deployments:</h3>
          <div v-for="deployment in configuration.deployments" :key="deployment.id">
            <router-link :to="`/results/${deployment.id}`">
              <Button
                :label="deployment.time"
                size="small"
                class="chip-deployed"
                :title="`View Deployment ${deployment.time}`"
              />
            </router-link>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>
