<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import MultiSelect from 'primevue/multiselect'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import CodeEditor from '../components/CodeEditor.vue'
import { getIoTDevices, deployIoTInference } from '../api'
import { useNotify } from '../notify'
import type { IoTDevice } from '../types'

const route = useRoute()
const router = useRouter()
const notify = useNotify()

const resultID = Number(route.params.id)
const availableDevices = ref<IoTDevice[]>([])

const form = ref({
  device_token: [] as string[],
  code: '',
  applyIntQuant: false
})

onMounted(async () => {
  try {
    const devices = await getIoTDevices()
    availableDevices.value = devices.filter((d) => d.status === 'connected')
  } catch {
    notify.error('Error fetching devices')
  }
})

const formInvalid = computed(() => form.value.device_token.length === 0 || !form.value.code)

async function onSubmit() {
  // Backend contract (iot_devices.py): keys are 'code', 'device_token',
  // 'model_result' and 'applyIntQuant'.
  const payload = { ...form.value, model_result: resultID }
  try {
    await deployIoTInference(resultID, payload)
    notify.ok('Model deployed for inference')
    router.push('/results')
  } catch {
    notify.error('Error deploying the model for inference')
  }
}
</script>

<template>
  <div class="page">
    <Card class="form-card">
      <template #title>Deploy Training result {{ resultID }} for inference in Tasmota</template>
      <template #content>
        <form @submit.prevent="onSubmit" autocomplete="off">
          <div class="field">
            <label>Available Tasmotas for deploy *</label>
            <MultiSelect
              v-model="form.device_token"
              :options="availableDevices"
              optionValue="token"
              :optionLabel="(d: IoTDevice) => `${d.friendly_name} | ${d.token}`"
              placeholder="Select devices"
              display="chip"
            />
          </div>

          <div class="field">
            <label>Berry Script for Tasmota *</label>
            <CodeEditor v-model="form.code" language="lua" height="320px" />
          </div>

          <div class="field">
            <label><Checkbox v-model="form.applyIntQuant" binary /> Apply int8 quantization</label>
          </div>

          <div class="row-buttons">
            <Button label="Go Back" text @click="$router.back()" />
            <Button type="submit" label="Deploy" :disabled="formInvalid" />
          </div>
        </form>
      </template>
    </Card>
  </div>
</template>
