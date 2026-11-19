<script setup lang="ts">
import { Download, Trash2 } from '@lucide/vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import FormActions from '@/components/app/FormActions.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// 模块管理: 每个可选模块一张半行卡片(状态, 主机缺少的条件, 安装或卸载); 有任务时上方显示任务和安装输出.
interface ModuleInfo {
  key: string
  installed: boolean
  enabled: boolean
  needs: string
}
interface Modules {
  modules: ModuleInfo[]
  busy: boolean
  job: { module: string; action: string; state: string; text: string } | null
  progress: string | null
}

const { t } = useI18n()
const data = ref<Modules>()
const sending = ref(false)

const TITLES: Record<string, string> = { iperf3: 'legacy.iperf', proxy_nodes: 'legacy.proxy', caddy: 'legacy.domains' }
const NAMES: Record<string, string> = { frps: 'FRPS', frpc: 'FRPC', tailscale: 'Tailscale' }
const title = (key: string) => NAMES[key] ?? t(TITLES[key] ?? key)

// 有任务在运行时每 2 秒刷新; 任务结束后结果再显示 30 秒(服务器决定), 期间每 5 秒刷新一次直到消失
let timer: ReturnType<typeof setTimeout> | undefined
async function load() {
  clearTimeout(timer)
  try {
    data.value = await api<Modules>('modules')
  } catch (err) {
    if (isSignedOut(err)) return
  }
  if (!data.value || data.value.busy) timer = setTimeout(load, 2000)
  else if (data.value.job) timer = setTimeout(load, 5000)
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

const ERRORS: Record<string, string> = {
  module_busy: 'vps.dashboard.busy',
  module_job_failed: 'legacy.module_job_failed',
  module_source_missing: 'legacy.module_source_missing',
  module_tailscale_asset_missing: 'legacy.module_tailscale_asset_missing',
}
async function manage(module: string, action: 'install' | 'uninstall') {
  if (sending.value) return
  sending.value = true
  try {
    data.value = await api<Modules>('modules/manage', { method: 'POST', body: { module, action } })
    clearTimeout(timer)
    timer = setTimeout(load, 2000)
  } catch (err) {
    const code = err instanceof ApiError ? err.code : ''
    showToast(t(ERRORS[code] ?? 'vps.common.failed'), 'destructive')
  } finally {
    sending.value = false
  }
}

const status = (item: ModuleInfo) =>
  !item.installed ? t('legacy.module_not_installed') : item.enabled ? t('legacy.module_enabled') : t('legacy.module_disabled')
const tone = (item: ModuleInfo) => (!item.installed ? 'neutral' : item.enabled ? 'success' : 'warning')
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.modules')" :description="t('vps.modules.description')" :trail="[{ to: '/settings', label: t('page.settings') }]" />

    <PageSection v-if="data?.job" :cols="4" :title="t('vps.dashboard.job')">
      <AlertBanner :tone="data.job.state === 'failed' ? 'destructive' : data.job.state === 'done' ? 'success' : 'info'" role="status">{{ data.job.text }}</AlertBanner>
      <!-- 安装输出: 最后 20 行, 可以用键盘滚动 -->
      <LogOutput v-if="data.progress" :text="data.progress" :label="t('legacy.module_progress')" />
    </PageSection>

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <PageSection v-for="item in data?.modules ?? []" :key="item.key" :cols="2" :title="title(item.key)">
      <div>
        <StatusBadge :tone="tone(item)">{{ status(item) }}</StatusBadge>
      </div>
      <AlertBanner v-if="item.needs" tone="warning">{{ item.needs }}</AlertBanner>
      <FormActions>
        <ConfirmDialog
          v-if="item.installed"
          :title="t('vps.modules.uninstallTitle', { name: title(item.key) })"
          :description="t('legacy.module_uninstall_confirm', { name: title(item.key) })"
          :confirm-label="t('legacy.module_uninstall')"
          danger
          @confirm="manage(item.key, 'uninstall')"
        >
          <template #trigger>
            <Button variant="destructive" :disabled="sending || data?.busy" :aria-label="t('vps.modules.uninstall', { name: title(item.key) })">
              <Trash2 aria-hidden="true" />{{ t('legacy.module_uninstall') }}
            </Button>
          </template>
        </ConfirmDialog>
        <Button v-else :disabled="sending || data?.busy" :aria-label="t('vps.modules.install', { name: title(item.key) })" @click="manage(item.key, 'install')">
          <Download aria-hidden="true" />{{ t('legacy.module_install') }}
        </Button>
      </FormActions>
    </PageSection>
  </CardGrid>
</template>
