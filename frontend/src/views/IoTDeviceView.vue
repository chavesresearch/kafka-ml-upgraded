<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import { getIoTDevice, createIoTDevice, editIoTDevice } from '../api'
import { useNotify } from '../notify'

const route = useRoute()
const router = useRouter()
const notify = useNotify()

const deviceId = route.params.id ? Number(route.params.id) : undefined
const create = deviceId === undefined
const valid = ref(true)

const form = ref({
  friendly_name: '',
  mqtt_address: '',
  mqtt_port: '' as number | string,
  mqtt_username: '',
  mqtt_password: ''
})

onMounted(async () => {
  if (!create && deviceId !== undefined) {
    try {
      const device = await getIoTDevice(deviceId)
      form.value = {
        friendly_name: device.friendly_name,
        mqtt_address: device.mqtt_address,
        mqtt_port: device.mqtt_port,
        mqtt_username: device.mqtt_username,
        mqtt_password: device.mqtt_password
      }
    } catch {
      valid.value = false
      notify.error('Error IoT Device not found')
    }
  }
})

const formInvalid = computed(() => !form.value.friendly_name)

async function onSubmit() {
  try {
    if (create) {
      await createIoTDevice(form.value)
      notify.ok('IoT Device created')
    } else if (deviceId !== undefined) {
      await editIoTDevice(deviceId, form.value)
      notify.ok('IoT Device updated')
    }
    router.push('/devices')
  } catch (err) {
    notify.error(`Error ${create ? 'creating' : 'updating'} the IoT Device: ` + (err as Error).message)
  }
}
</script>

<template>
  <div class="page">
    <Card class="form-card">
      <template #title>{{ create ? 'Create IoT Device' : 'Edit IoT Device' }}</template>
      <template #content>
        <form @submit.prevent="onSubmit" autocomplete="off">
          <div class="field">
            <label>Friendly Name *</label>
            <InputText v-model="form.friendly_name" autofocus />
          </div>
          <div class="field">
            <label>MQTT Address</label>
            <InputText v-model="form.mqtt_address" />
          </div>
          <div class="field">
            <label>MQTT Port</label>
            <InputText v-model="form.mqtt_port as string" />
          </div>
          <div class="field">
            <label>MQTT User</label>
            <InputText v-model="form.mqtt_username" />
          </div>
          <div class="field">
            <label>MQTT Password</label>
            <Password v-model="form.mqtt_password" :feedback="false" toggleMask />
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
