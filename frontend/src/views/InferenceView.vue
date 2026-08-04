<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import { getInferenceInfo, getModelByResultId, deployInference } from '../api'
import { useNotify } from '../notify'
import type { InferencePayload } from '../types'

const route = useRoute()
const router = useRouter()
const notify = useNotify()

const resultID = Number(route.params.id)
const valid = ref(false)
const distributed = ref(false)

const form = ref({
  replicas: null as number | null,
  input_format: '',
  input_config: '',
  input_kafka_broker: '',
  input_topic: '',
  output_kafka_broker: '',
  output_topic: '',
  upper_kafka_broker: '',
  output_upper: '',
  external_host: '',
  token: '',
  limit: '' as number | string,
  gpumem: null as number | null
})

onMounted(async () => {
  try {
    const info = await getInferenceInfo(resultID)
    if (info.input_format !== '') {
      form.value.input_format = info.input_format
      form.value.input_config = info.input_config
      notify.ok('Input format and configuration found from another dataset/inference')
    }
    valid.value = true
  } catch {
    notify.error('The training result does not exist')
  }
  try {
    const model = await getModelByResultId(resultID)
    // Only sub-models below the top of a distributed chain forward partial
    // predictions to an upper model.
    distributed.value = Boolean(model.distributed && model.father != null)
  } catch {
    valid.value = false
    notify.error('Error model not found')
  }
})

const formInvalid = computed(() => {
  const f = form.value
  if (f.replicas == null || !f.input_format || !f.input_config) return true
  if (!f.input_topic || !f.output_topic || f.gpumem == null) return true
  if (distributed.value && (!f.output_upper || f.limit === '')) return true
  return false
})

async function onSubmit() {
  const payload: InferencePayload = { ...form.value, model_result: resultID }
  if (!distributed.value) {
    delete payload.upper_kafka_broker
    delete payload.output_upper
    delete payload.limit
  }
  try {
    await deployInference(resultID, payload)
    notify.ok('Model deployed for inference')
    router.push('/inferences')
  } catch {
    notify.error('Error deploying the model for inference')
  }
}
</script>

<template>
  <div class="page">
    <Card class="form-card">
      <template #title>Deploy Training result {{ resultID }} for inference</template>
      <template #content>
        <form @submit.prevent="onSubmit" autocomplete="off">
          <div class="field">
            <label>Number of replicas *</label>
            <InputNumber v-model="form.replicas" placeholder="1" :useGrouping="false" />
          </div>
          <div class="field">
            <label>Input format of data *</label>
            <InputText v-model="form.input_format" placeholder="RAW" />
          </div>
          <div class="field">
            <label>Configuration for input data *</label>
            <InputText
              v-model="form.input_config"
              placeholder='{"data_type": "", "label_type": "", "data_reshape": "", "label_reshape": ""}'
            />
          </div>
          <div class="field">
            <label>Kafka broker for input data</label>
            <InputText
              v-model="form.input_kafka_broker"
              placeholder="Input kafka broker (e.g. https://192.168.65.3:9094)"
            />
          </div>
          <div class="field">
            <label>Kafka topic for input data *</label>
            <InputText v-model="form.input_topic" placeholder="input_topic" />
          </div>
          <div class="field">
            <label>Kafka broker for output data</label>
            <InputText
              v-model="form.output_kafka_broker"
              placeholder="Output kafka broker (e.g. https://192.168.65.3:9094)"
            />
          </div>
          <div class="field">
            <label>Kafka output topic for predictions *</label>
            <InputText v-model="form.output_topic" placeholder="output_topic" />
          </div>
          <template v-if="distributed">
            <div class="field">
              <label>Kafka broker for upper data</label>
              <InputText
                v-model="form.upper_kafka_broker"
                placeholder="Upper kafka broker (e.g. https://192.168.65.3:9094)"
              />
            </div>
            <div class="field">
              <label>Kafka output topic for upper model *</label>
              <InputText v-model="form.output_upper" placeholder="output_upper" />
            </div>
            <div class="field">
              <label>Prediction limit *</label>
              <InputText v-model="form.limit as string" placeholder="limit" />
            </div>
          </template>
          <div class="field">
            <label>Kubernetes Cluster Host</label>
            <InputText
              v-model="form.external_host"
              placeholder="External Host (e.g. https://192.168.65.3:6443)"
            />
          </div>
          <div class="field">
            <label>Kubernetes Cluster Token</label>
            <InputText v-model="form.token" placeholder="Token" />
          </div>
          <div class="field">
            <label>GPU Memory usage estimation (Kubernetes Scheduler) *</label>
            <InputNumber v-model="form.gpumem" placeholder="0" :useGrouping="false" />
          </div>

          <div class="row-buttons">
            <Button label="Go Back" text @click="$router.back()" />
            <Button v-if="valid" type="submit" label="Deploy" :disabled="formInvalid" />
          </div>
        </form>
      </template>
    </Card>
  </div>
</template>
