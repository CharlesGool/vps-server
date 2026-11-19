<script setup lang="ts">
import { Save } from '@lucide/vue'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageSection from '@/components/app/PageSection.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import { Button } from '@/components/ui/button'
import { api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 资源监控页底部的告警设置, 两张整行卡片. 开关立即生效(设置行样式); 阈值是表单, 点保存提交. 告警经安全设置里的 Bark 推送, 同一事件一天最多一次.
interface Alerts {
  enabled: boolean
  services: boolean
  disk: number
  memory: number
  cpu: number
  cpu_minutes: number
  gpu_temp: number
  gpu_memory: number
}
const { t } = useI18n()
const alerts = ref<Alerts>()
const barkReady = ref(true)
const hasGpu = ref(false)
const form = ref({ disk: 90, memory: 95, cpu: 95, cpu_minutes: 10, gpu_temp: 85, gpu_memory: 95 })
const busy = ref(false)

function apply(value: { alerts: Alerts; barkReady: boolean; hasGpu?: boolean }) {
  alerts.value = value.alerts
  barkReady.value = value.barkReady
  hasGpu.value = !!value.hasGpu
  form.value = { disk: value.alerts.disk, memory: value.alerts.memory, cpu: value.alerts.cpu, cpu_minutes: value.alerts.cpu_minutes, gpu_temp: value.alerts.gpu_temp, gpu_memory: value.alerts.gpu_memory }
}

async function load() {
  try {
    apply(await api<{ alerts: Alerts; barkReady: boolean }>('monitor/alerts'))
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)

async function save(change: Partial<Alerts>, toast = true) {
  if (!alerts.value) return
  busy.value = true
  try {
    apply(await api<{ alerts: Alerts; barkReady: boolean }>('monitor/alerts', { method: 'PUT', body: { alerts: { ...alerts.value, ...change } } }))
    if (toast) showToast(t('vps.monitor.alertsSaved'), 'success')
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <template v-if="alerts">
    <PageSection :cols="4" :title="t('vps.monitor.alertSwitches')" :description="t('vps.monitor.alertsDescription')">
      <AlertBanner v-if="!barkReady" tone="warning">{{ t('vps.monitor.barkMissing') }}</AlertBanner>
      <SwitchField
        :model-value="alerts.enabled"
        :label="t('vps.monitor.alertEnabled')"
        :description="t('vps.monitor.alertEnabledHelp')"
        :disabled="busy"
        @update:model-value="save({ enabled: $event }, false)"
      />
      <SwitchField
        :model-value="alerts.services"
        :label="t('vps.monitor.alertServices')"
        :description="t('vps.monitor.alertServicesHelp')"
        :disabled="busy || !alerts.enabled"
        @update:model-value="save({ services: $event }, false)"
      />
    </PageSection>

    <CardForm @submit.prevent="save(form)">
      <PageSection :cols="4" :title="t('vps.monitor.thresholds')" :description="t('vps.monitor.thresholdsHelp')">
        <FormField v-slot="field" :label="t('vps.monitor.diskThreshold')" :span="6">
          <NumberField :id="field.id" v-model="form.disk" :min="50" :max="99" unit="%" :disabled="!alerts.enabled" />
        </FormField>
        <FormField v-slot="field" :label="t('vps.monitor.memoryThreshold')" :span="6">
          <NumberField :id="field.id" v-model="form.memory" :min="50" :max="99" unit="%" :disabled="!alerts.enabled" />
        </FormField>
        <FormField v-slot="field" :label="t('vps.monitor.cpuThreshold')" :span="6">
          <NumberField :id="field.id" v-model="form.cpu" :min="50" :max="100" unit="%" :disabled="!alerts.enabled" />
        </FormField>
        <FormField v-slot="field" :label="t('vps.monitor.cpuMinutes')" :span="6">
          <NumberField :id="field.id" v-model="form.cpu_minutes" :min="1" :max="120" :unit="t('vps.monitor.minutesUnit')" :disabled="!alerts.enabled" />
        </FormField>
        <template v-if="hasGpu">
          <FormField v-slot="field" :label="t('vps.monitor.gpuTempThreshold')" :span="6">
            <NumberField :id="field.id" v-model="form.gpu_temp" :min="50" :max="110" unit="°C" :disabled="!alerts.enabled" />
          </FormField>
          <FormField v-slot="field" :label="t('vps.monitor.gpuMemoryThreshold')" :span="6">
            <NumberField :id="field.id" v-model="form.gpu_memory" :min="50" :max="99" unit="%" :disabled="!alerts.enabled" />
          </FormField>
        </template>
        <FormActions>
          <Button type="submit" :disabled="busy || !alerts.enabled"><Save aria-hidden="true" />{{ t('vps.common.save') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>
  </template>
</template>
