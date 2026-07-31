<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import RadioButton from 'primevue/radiobutton'
import Dropdown from 'primevue/dropdown'
import InputSwitch from 'primevue/inputswitch'
import Button from 'primevue/button'
import {
  getConfiguration,
  getFrameworksInConfiguration,
  getDistributedConfiguration,
  deploy
} from '../api'
import { enableFederatedBlockchain } from '../env'
import { useNotify } from '../notify'
import {
  KWARGS_RE,
  showIndefinite as showIndefiniteFn,
  showBlockchainToggle as showBlockchainToggleFn,
  showIndefiniteFields as showIndefiniteFieldsFn,
  isDeploymentFormInvalid,
  buildDeploymentPayload,
  type DeploymentForm
} from '../logic/deployment'
import type { Configuration } from '../types'

const route = useRoute()
const router = useRouter()
const notify = useNotify()

const configurationID = Number(route.params.id)
const configuration = ref<Partial<Configuration>>({})
const valid = ref(false)
const detectedFrameworks = ref<string[]>([])
const showDistributed = ref(false)

const strategies = [{ value: 'FedAvg', label: 'Federated Averaging strategy' }]

const form = ref<DeploymentForm>({
  unsupervised: false,
  incremental: false,
  federated: false,
  indefinite: false,
  blockchain: false,
  batch: null,
  tf_kwargs_fit: '',
  tf_kwargs_val: '',
  pth_kwargs_fit: '',
  pth_kwargs_val: '',
  unsupervised_rounds: null,
  confidence: null,
  optimizer: '',
  learning_rate: '',
  loss: '',
  metrics: '',
  stream_timeout: null,
  monitoring_metric: '',
  change: '',
  improvement: '',
  gpumem: null,
  agg_rounds: null,
  min_data: null,
  data_restriction: '',
  agg_strategy: null,
  conf_mat_settings: false
})

onMounted(async () => {
  try {
    configuration.value = await getConfiguration(configurationID)
    valid.value = true
    detectedFrameworks.value = await getFrameworksInConfiguration(configurationID)
    showDistributed.value = Boolean(await getDistributedConfiguration(configurationID))
  } catch {
    notify.error('Configuration not found')
  }
})

const hasTf = computed(() => detectedFrameworks.value.includes('tf'))
const hasPth = computed(() => detectedFrameworks.value.includes('pth'))
const showIndefinite = computed(() => showIndefiniteFn(form.value))
const showBlockchainToggle = computed(() =>
  showBlockchainToggleFn(form.value, enableFederatedBlockchain)
)
const showIndefiniteFields = computed(() => showIndefiniteFieldsFn(form.value))

const tfKwargsFitInvalid = computed(() => hasTf.value && !KWARGS_RE.test(form.value.tf_kwargs_fit || ''))
const tfKwargsValInvalid = computed(() => hasTf.value && !KWARGS_RE.test(form.value.tf_kwargs_val || ''))
const pthKwargsFitInvalid = computed(() => hasPth.value && !KWARGS_RE.test(form.value.pth_kwargs_fit || ''))
const pthKwargsValInvalid = computed(() => hasPth.value && !KWARGS_RE.test(form.value.pth_kwargs_val || ''))

const formInvalid = computed(() =>
  isDeploymentFormInvalid(form.value, {
    detectedFrameworks: detectedFrameworks.value,
    hasTf: hasTf.value,
    hasPth: hasPth.value
  })
)

async function onSubmit() {
  const payload = buildDeploymentPayload(form.value, {
    configurationID,
    showDistributed: showDistributed.value,
    enableFederatedBlockchain
  })
  try {
    await deploy(payload)
    router.push('/deployments')
  } catch (err) {
    notify.error('Error deploying the configuration: ' + (err as Error).message)
  }
}
</script>

<template>
  <div class="page">
    <Card class="form-card">
      <template #title>Deploy configuration {{ configuration.name }}</template>
      <template #content>
        <form @submit.prevent="onSubmit" autocomplete="off">
          <div class="field">
            <label><Checkbox v-model="form.unsupervised" binary /> Semi-supervised training</label>
          </div>
          <div class="field field-row">
            <label><Checkbox v-model="form.incremental" binary /> Incremental training</label>
            <label><Checkbox v-model="form.federated" binary /> Federated learning</label>
          </div>
          <div class="field" v-if="showIndefinite">
            <label><Checkbox v-model="form.indefinite" binary /> Indefinite training</label>
          </div>
          <div class="field" v-if="showBlockchainToggle">
            <label><Checkbox v-model="form.blockchain" binary /> Blockchain-traced training</label>
          </div>

          <h4>Model training settings</h4>

          <div class="field" v-if="detectedFrameworks.length > 0">
            <label>Batch size for training *</label>
            <InputNumber v-model="form.batch" placeholder="10" :useGrouping="false" />
          </div>

          <template v-if="hasTf">
            <div class="field">
              <label>TensorFlow Training configuration *</label>
              <InputText v-model="form.tf_kwargs_fit" placeholder="epochs=5" />
              <span class="text-danger" v-if="form.tf_kwargs_fit && tfKwargsFitInvalid">
                Use the format: key=value, key=value
              </span>
            </div>
            <div class="field">
              <label>TensorFlow Validation configuration</label>
              <InputText v-model="form.tf_kwargs_val" />
              <span class="text-danger" v-if="form.tf_kwargs_val && tfKwargsValInvalid">
                Use the format: key=value, key=value
              </span>
            </div>
          </template>

          <template v-if="hasPth">
            <div class="field">
              <label>PyTorch Training configuration *</label>
              <InputText v-model="form.pth_kwargs_fit" placeholder="max_epochs=5" />
            </div>
            <div class="field">
              <label>PyTorch Validation configuration</label>
              <InputText v-model="form.pth_kwargs_val" />
            </div>
          </template>

          <template v-if="form.unsupervised">
            <h4>Unsupervised models settings</h4>
            <div class="field" v-if="!form.incremental">
              <label>Unsupervised rounds</label>
              <InputNumber v-model="form.unsupervised_rounds" placeholder="5" :useGrouping="false" />
            </div>
            <div class="field">
              <label>Confidence</label>
              <InputNumber
                v-model="form.confidence"
                placeholder="0.9"
                :maxFractionDigits="5"
                :useGrouping="false"
              />
            </div>
          </template>

          <template v-if="showDistributed">
            <h4>Distributed models settings</h4>
            <div class="field">
              <label>Optimizer</label>
              <InputText v-model="form.optimizer" placeholder="adam" />
            </div>
            <div class="field">
              <label>Learning rate</label>
              <InputText v-model="form.learning_rate as string" placeholder="0.001" />
            </div>
            <div class="field">
              <label>Loss function</label>
              <InputText v-model="form.loss" placeholder="sparse_categorical_crossentropy" />
            </div>
            <div class="field">
              <label>Metrics (splitted by comas)</label>
              <InputText v-model="form.metrics" placeholder="sparse_categorical_accuracy" />
            </div>
          </template>

          <template v-if="form.incremental">
            <h4>Incremental training settings</h4>
            <div class="field" v-if="!form.indefinite">
              <label>Stream timeout (in milliseconds)</label>
              <InputNumber v-model="form.stream_timeout" placeholder="60000" :useGrouping="false" />
            </div>
            <template v-if="showIndefiniteFields">
              <div class="field">
                <label>Monitoring metric (must match with a predefined metric) *</label>
                <InputText v-model="form.monitoring_metric" />
              </div>
              <div class="field">
                <label>If the monitoring metric improves, does it increase or decrease? *</label>
                <div class="field-row">
                  <label><RadioButton v-model="form.change" value="up" /> Increase</label>
                  <label><RadioButton v-model="form.change" value="down" /> Decrease</label>
                </div>
              </div>
              <div class="field">
                <label>Improvement</label>
                <InputText v-model="form.improvement as string" placeholder="0.05" />
              </div>
            </template>
          </template>

          <div class="field" v-if="detectedFrameworks.length > 0">
            <label>GPU Memory usage estimation in GB (Kubernetes Scheduler) *</label>
            <InputNumber v-model="form.gpumem" placeholder="0" :useGrouping="false" />
          </div>

          <template v-if="form.federated">
            <h4>Federated strategy settings</h4>
            <div class="field">
              <label>Number of aggregation rounds *</label>
              <InputNumber v-model="form.agg_rounds" placeholder="15" :useGrouping="false" />
            </div>
            <div class="field" v-if="!form.incremental">
              <label>Minimun data entries per device *</label>
              <InputNumber v-model="form.min_data" placeholder="1000" :useGrouping="false" />
            </div>
            <div class="field">
              <label>Data Restriction *</label>
              <InputText v-model="form.data_restriction" placeholder="{}" />
            </div>
            <div class="field">
              <label>Aggregation strategy *</label>
              <Dropdown
                v-model="form.agg_strategy"
                :options="strategies"
                optionValue="value"
                optionLabel="label"
              />
            </div>
          </template>

          <div
            class="field"
            v-if="detectedFrameworks.length > 0 && !form.incremental && !form.federated"
          >
            <label style="display: flex; align-items: center; gap: 0.6rem">
              <InputSwitch v-model="form.conf_mat_settings" />
              Create confusion matrix at end (if test set is specified)
            </label>
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
