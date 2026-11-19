<script setup lang="ts">
import { Download } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import FormActions from '@/components/app/FormActions.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import PageSection from '@/components/app/PageSection.vue'
import { Button } from '@/components/ui/button'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 功能页在模块还没安装时显示的卡片: 主机缺少的条件, 安装按钮, 安装任务的状态和输出.
// 安装完成后发出 installed, 页面重新加载自己的数据. module 是模块管理里的键(如 'iperf3'), name 是显示名称.
interface ModuleInfo {
  key: string
  installed: boolean
  needs: string
}
interface Modules {
  modules: ModuleInfo[]
  busy: boolean
  job: { module: string; action: string; state: string; text: string } | null
  progress: string | null
}

const props = defineProps<{ module: string; name: string }>()
const emit = defineEmits<{ installed: [] }>()
const { t } = useI18n()
const data = ref<Modules>()
const sending = ref(false)
const item = computed(() => data.value?.modules.find((entry) => entry.key === props.module))
// 只显示这个模块的安装任务
const job = computed(() => (data.value?.job?.module === props.module && data.value.job.action === 'install' ? data.value.job : null))

let timer: ReturnType<typeof setTimeout> | undefined
async function load() {
  clearTimeout(timer)
  try {
    data.value = await api<Modules>('modules')
  } catch (err) {
    if (isSignedOut(err)) return
  }
  if (item.value?.installed && !data.value?.busy) {
    emit('installed')
    return
  }
  if (!data.value || data.value.busy) timer = setTimeout(load, 2000)
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

const ERRORS: Record<string, string> = {
  module_busy: 'vps.dashboard.busy',
  module_job_failed: 'console.module_job_failed',
  module_source_missing: 'console.module_source_missing',
  module_tailscale_asset_missing: 'console.module_tailscale_asset_missing',
}
async function install() {
  if (sending.value) return
  sending.value = true
  try {
    data.value = await api<Modules>('modules/manage', { method: 'POST', body: { module: props.module, action: 'install' } })
    clearTimeout(timer)
    timer = setTimeout(load, 2000)
  } catch (err) {
    const code = err instanceof ApiError ? err.code : ''
    showToast(t(ERRORS[code] ?? 'vps.common.failed'), 'destructive')
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <PageSection :cols="2" :col="2" :title="name" :description="t('console.module_not_installed')">
    <AlertBanner v-if="job" :tone="job.state === 'failed' ? 'destructive' : job.state === 'done' ? 'success' : 'info'" role="status">{{ job.text }}</AlertBanner>
    <LogOutput v-if="job && data?.progress" :text="data.progress" :label="t('console.module_progress')" />
    <AlertBanner v-if="item?.needs && !job" tone="warning">{{ item.needs }}</AlertBanner>
    <FormActions>
      <Button :disabled="sending || !data || data.busy" @click="install">
        <Download aria-hidden="true" />{{ t('vps.modules.install', { name }) }}
      </Button>
    </FormActions>
  </PageSection>
</template>
