<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useConfirm } from 'primevue/useconfirm'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import {
  getDeployments,
  getDeploymentsOfConfiguration,
  getConfiguration,
  deleteDeployment
} from '../api'
import { useNotify } from '../notify'
import type { Configuration, DeploymentInfo } from '../types'

const route = useRoute()
const router = useRouter()
const notify = useNotify()
const confirm = useConfirm()

const configurationID = route.params.id ? Number(route.params.id) : undefined
const configuration = ref<Configuration | null>(null)
const deployments = ref<DeploymentInfo[]>([])
const filter = ref('')

onMounted(async () => {
  try {
    if (configurationID !== undefined) {
      configuration.value = await getConfiguration(configurationID)
      deployments.value = await getDeploymentsOfConfiguration(configurationID)
    } else {
      deployments.value = await getDeployments()
    }
  } catch {
    notify.error('Error connecting with the server')
  }
})

const filtered = computed(() => {
  const text = filter.value.trim().toLowerCase()
  if (!text) return deployments.value
  return deployments.value.filter((d) =>
    Object.values(d).some((v) => String(v).toLowerCase().includes(text))
  )
})

const menuRef = ref<InstanceType<typeof Menu> | null>(null)
const menuItems = ref<MenuItem[]>([])

function openMenu(event: Event, deployment: DeploymentInfo) {
  menuItems.value = [
    { label: 'Results', icon: 'pi pi-eye', command: () => router.push(`/results/${deployment.id}`) },
    { label: 'Remove', icon: 'pi pi-trash', command: () => confirmDelete(deployment.id) }
  ]
  menuRef.value?.toggle(event)
}

function confirmDelete(id: number) {
  confirm.require({
    header: 'Are you sure?',
    message: `You will remove Deployment ${id}`,
    accept: async () => {
      try {
        await deleteDeployment(id)
        deployments.value = deployments.value.filter((d) => d.id !== id)
        notify.ok('Deployment deleted')
      } catch (err) {
        notify.error('Error deleting the deployment: ' + (err as Error).message)
      }
    }
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h1>
        Deployments
        <span v-if="configuration" class="subtitle"> of Configuration {{ configuration.name }}</span>
      </h1>
    </div>

    <div class="field">
      <InputText v-model="filter" placeholder="Filter" />
    </div>

    <Menu ref="menuRef" :model="menuItems" popup />

    <div class="card-grid">
      <Card v-for="deployment in filtered" :key="deployment.id" class="dashboard-card surface">
        <template #title>
          <div class="card-title-row">
            <div class="title">
              <h3>Deployment {{ deployment.id }}</h3>
              <h6>{{ deployment.time }}</h6>
            </div>
            <Button icon="pi pi-ellipsis-v" text @click="openMenu($event, deployment)" />
          </div>
        </template>
        <template #content>
          <h3>Training results</h3>
          <div v-for="result in deployment.results" :key="result.id">
            <router-link :to="`/results/${deployment.id}`">
              <Button
                :label="`Model ${result.model.name}, last change ${result.status_changed}`"
                size="small"
                :class="`chip-${result.status}`"
                :title="`Result ${result.id} status ${result.status}`"
              />
            </router-link>
          </div>
          <h3>Configuration:</h3>
          <router-link :to="`/configuration/${deployment.configuration.id}`">
            <Button :label="deployment.configuration.name" size="small" outlined />
          </router-link>
          <h3>Batch size:</h3>
          <p>{{ deployment.batch }}</p>
          <template v-if="deployment.tf_kwargs_fit">
            <h3>TF Training arguments:</h3>
            <p>{{ deployment.tf_kwargs_fit }}</p>
          </template>
          <template v-if="deployment.tf_kwargs_val">
            <h3>TF Validation arguments:</h3>
            <p>{{ deployment.tf_kwargs_val }}</p>
          </template>
          <template v-if="deployment.pth_kwargs_fit">
            <h3>PTH Training arguments:</h3>
            <p>{{ deployment.pth_kwargs_fit }}</p>
          </template>
          <template v-if="deployment.pth_kwargs_val">
            <h3>PTH Validation arguments:</h3>
            <p>{{ deployment.pth_kwargs_val }}</p>
          </template>
        </template>
      </Card>
    </div>
  </div>
</template>
