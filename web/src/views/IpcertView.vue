<script setup lang="ts">
import { ShieldCheck, ShieldOff } from '@lucide/vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import ModuleInstall from '@/components/vps/ModuleInstall.vue'
import { Button } from '@/components/ui/button'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// IP 证书: 控制台在本机公网 IPv4 上使用 Let's Encrypt 证书. 开关作为模块任务在后台进行, 进行中每 3 秒刷新.
interface Ipcert {
  installed: boolean
  enabled?: boolean
  facts?: { url: string; issuer: string; expires: string } | null
  job?: 'running' | 'failed' | null
}
const { t } = useI18n()
const data = ref<Ipcert>()
const busy = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function load() {
  clearTimeout(timer)
  try {
    data.value = await api<Ipcert>('ipcert')
  } catch (err) {
    if (isSignedOut(err)) return
  }
  if (!data.value || data.value.job === 'running') timer = setTimeout(load, 3000)
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

const ERRORS: Record<string, string> = {
  module_busy: 'vps.dashboard.busy',
  module_job_failed: 'legacy.module_job_failed',
  module_source_missing: 'legacy.module_source_missing',
}
async function toggle(enable: boolean) {
  busy.value = true
  try {
    await api('modules/action', { method: 'POST', body: { module: 'ipcert', action: enable ? 'enable' : 'disable' } })
    await load()
  } catch (err) {
    const code = err instanceof ApiError ? err.code : ''
    if (!isSignedOut(err)) showToast(t(ERRORS[code] ?? 'vps.common.failed'), 'destructive')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('legacy.ipcert')" :description="t('vps.ipcert.description')" />
    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>
    <ModuleInstall v-else-if="!data.installed" module="ipcert" :name="t('legacy.ipcert')" @installed="load" />
    <PageSection v-else :cols="4" :title="t('legacy.domains_ip_heading')" :description="t('legacy.domains_ip_help')">
      <InlineGroup>
        <StatusBadge :tone="data.enabled ? 'success' : 'neutral'">{{ t(data.enabled ? 'legacy.domains_ip_on' : 'legacy.ipcert_off') }}</StatusBadge>
      </InlineGroup>
      <AlertBanner v-if="data.job === 'running'" tone="info">{{ t('legacy.module_job_running') }}</AlertBanner>
      <AlertBanner v-else-if="data.job === 'failed'" tone="destructive">{{ t('legacy.ipcert_failed') }}</AlertBanner>
      <DescriptionList
        v-if="data.facts"
        :items="[
          { key: 'url', label: t('legacy.ipcert_address'), value: data.facts.url, mono: true, copyable: true },
          { key: 'issuer', label: t('legacy.ipcert_issuer'), value: data.facts.issuer },
          { key: 'expires', label: t('legacy.ipcert_expires'), value: data.facts.expires },
        ]"
      />
      <p class="text-sm text-muted-foreground">{{ t('legacy.ipcert_ports') }}</p>
      <FormActions>
        <ConfirmDialog
          v-if="data.enabled"
          :title="t('legacy.domains_ip_disable')"
          :description="t('legacy.domains_ip_off_confirm')"
          :confirm-label="t('legacy.domains_ip_disable')"
          danger
          @confirm="toggle(false)"
        >
          <template #trigger>
            <Button variant="destructive" :disabled="busy || data.job === 'running'"><ShieldOff aria-hidden="true" />{{ t('legacy.domains_ip_disable') }}</Button>
          </template>
        </ConfirmDialog>
        <Button v-else :disabled="busy || data.job === 'running'" @click="toggle(true)"><ShieldCheck aria-hidden="true" />{{ t('legacy.domains_ip_enable') }}</Button>
      </FormActions>
    </PageSection>
  </CardGrid>
</template>
