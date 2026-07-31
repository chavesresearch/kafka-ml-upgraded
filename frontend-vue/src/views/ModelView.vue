<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import RadioButton from 'primevue/radiobutton'
import Checkbox from 'primevue/checkbox'
import Dropdown from 'primevue/dropdown'
import Button from 'primevue/button'
import CodeEditor from '../components/CodeEditor.vue'
import { getModel, getDistributedModels, createModel, editModel } from '../api'
import { useNotify } from '../notify'
import type { Framework, ModelPayload, SimpleModel } from '../types'

const TF_PLACEHOLDER = `model = tf.keras.models.Sequential([
  tf.keras.layers.Flatten(input_shape=(28, 28)),
  tf.keras.layers.Dense(128, activation='relu'),
  tf.keras.layers.Dense(10, activation='softmax')
])
model.compile(optimizer=tf.keras.optimizers.Adam(0.001),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=[tf.keras.metrics.SparseCategoricalAccuracy()])`

const PTH_PLACEHOLDER = `class NeuralNetwork(nn.Module):
    def __init__(self): ...
    def forward(self, x): ...
    def loss_fn(self): ...
    def optimizer(self): ...
    def metrics(self): ...

model = NeuralNetwork()`

const route = useRoute()
const router = useRouter()
const notify = useNotify()

const modelId = route.params.id ? Number(route.params.id) : undefined
const create = modelId === undefined
const valid = ref(true)

const form = ref({
  name: '',
  description: '',
  framework: '' as Framework | '',
  distributed: false,
  father: null as number | null,
  imports: '',
  code: ''
})
const distributedModels = ref<SimpleModel[]>([])

onMounted(async () => {
  if (!create && modelId !== undefined) {
    try {
      const model = await getModel(modelId)
      form.value = {
        name: model.name,
        description: model.description,
        framework: model.framework,
        distributed: model.distributed,
        father: model.father ? model.father.id : null,
        imports: model.imports,
        code: model.code
      }
    } catch {
      valid.value = false
      notify.error('Error model not found')
    }
  }
  try {
    distributedModels.value = await getDistributedModels()
  } catch {
    notify.error('Error connecting with the server')
  }
})

const placeholder = computed(() => {
  if (form.value.framework === 'tf') return TF_PLACEHOLDER
  if (form.value.framework === 'pth') return PTH_PLACEHOLDER
  return ''
})

const formInvalid = computed(() => !form.value.name || !form.value.framework || !form.value.code)

function fatherName(id: number | null): string {
  if (id == null) return ''
  return distributedModels.value.find((m) => m.id === id)?.name ?? ''
}

async function onSubmit() {
  const f = form.value
  const payload: ModelPayload = {
    name: f.name,
    description: f.description,
    framework: f.framework as Framework,
    imports: f.imports,
    code: f.code
  }
  // Distributed models are a TensorFlow-only feature (same as the Angular form).
  if (f.framework === 'tf') {
    payload.distributed = f.distributed
    if (f.distributed && f.father != null) payload.father = f.father
  }
  try {
    if (create) {
      await createModel(payload)
      notify.ok('Model created')
    } else if (modelId !== undefined) {
      await editModel(modelId, payload)
      notify.ok('Model updated')
    }
    router.push('/models')
  } catch (err) {
    notify.error(`Error ${create ? 'creating' : 'updating'} the model: ` + (err as Error).message)
  }
}
</script>

<template>
  <div class="page">
    <Card class="form-card">
      <template #title>{{ create ? 'Create Model' : `Edit Model ${modelId}` }}</template>
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
            <label>Select ML Framework *</label>
            <div class="field-row">
              <label><RadioButton v-model="form.framework" value="tf" /> TensorFlow</label>
              <label><RadioButton v-model="form.framework" value="pth" /> PyTorch (Ignite)</label>
            </div>
          </div>

          <div class="field" v-if="form.framework === 'tf'">
            <label><Checkbox v-model="form.distributed" binary /> Distributed</label>
          </div>

          <div class="field" v-if="form.framework === 'tf' && form.distributed">
            <label>Upper model</label>
            <Dropdown
              v-model="form.father"
              :options="distributedModels"
              optionValue="id"
              showClear
              placeholder="None (top of the chain)"
            >
              <template #option="{ option }">ID{{ option.id }} {{ option.name }}</template>
              <template #value="{ value }">
                <span v-if="value != null">ID{{ value }} {{ fatherName(value) }}</span>
                <span v-else>None (top of the chain)</span>
              </template>
            </Dropdown>
          </div>

          <div class="field">
            <label for="imports">Imports</label>
            <CodeEditor v-model="form.imports" language="python" height="90px" placeholder="import ..." />
          </div>

          <div class="field">
            <label for="code">Code *</label>
            <CodeEditor v-model="form.code" language="python" height="360px" :placeholder="placeholder" />
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
