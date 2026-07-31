<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import MultiSelect from 'primevue/multiselect'
import Button from 'primevue/button'
import { getFatherModels, getConfiguration, createConfiguration, editConfiguration } from '../api'
import { useNotify } from '../notify'
import type { SimpleModel } from '../types'

const route = useRoute()
const router = useRouter()
const notify = useNotify()

const configurationId = route.params.id ? Number(route.params.id) : undefined
const create = configurationId === undefined
const valid = ref(true)

const form = ref({ name: '', description: '', ml_models: [] as number[] })
// Only models at the top of a distributed chain (or plain models) are selectable.
const models = ref<SimpleModel[]>([])

// Exposed for tests only, to set/read form state without driving PrimeVue's
// MultiSelect overlay through the DOM.
defineExpose({ form })

onMounted(async () => {
  try {
    models.value = await getFatherModels()
  } catch {
    notify.error('Error connecting with the server')
  }
  if (!create && configurationId !== undefined) {
    try {
      const configuration = await getConfiguration(configurationId)
      form.value = {
        name: configuration.name,
        description: configuration.description,
        ml_models: (configuration.ml_models || []).map((m) => (typeof m === 'number' ? m : m.id))
      }
    } catch {
      valid.value = false
      notify.error('Error configuration not found')
    }
  }
})

const formInvalid = computed(() => !form.value.name || form.value.ml_models.length === 0)

async function onSubmit() {
  try {
    if (create) {
      await createConfiguration(form.value)
      notify.ok('Configuration created')
    } else if (configurationId !== undefined) {
      await editConfiguration(configurationId, form.value)
      notify.ok('Configuration updated')
    }
    router.push('/configurations')
  } catch (err) {
    notify.error(`Error ${create ? 'creating' : 'updating'} the configuration: ` + (err as Error).message)
  }
}
</script>

<template>
  <div class="page">
    <Card class="form-card">
      <template #title>{{ create ? 'Create Configuration' : 'Edit Configuration' }}</template>
      <template #content>
        <form @submit.prevent="onSubmit" autocomplete="off">
          <div class="field">
            <label for="name">Name *</label>
            <InputText id="name" v-model="form.name" autofocus />
          </div>

          <div class="field">
            <label for="description">Description</label>
            <InputText id="description" v-model="form.description" />
          </div>

          <div class="field">
            <label>ML Models *</label>
            <MultiSelect
              v-model="form.ml_models"
              :options="models"
              optionValue="id"
              :optionLabel="(m: SimpleModel) => `ID${m.id} ${m.name}`"
              placeholder="Select models"
              display="chip"
            />
          </div>

          <div class="row-buttons">
            <Button label="Go Back" text @click="$router.back()" />
            <Button
              v-if="valid"
              type="submit"
              :label="create ? 'Create' : 'Edit'"
              :disabled="formInvalid"
            />
          </div>
        </form>
      </template>
    </Card>
  </div>
</template>
