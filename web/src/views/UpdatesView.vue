<script setup lang="ts">
import { PackageCheck, RefreshCw } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import { Button } from '@/components/ui/button'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import { api } from '@/lib/api'
import { useSecurePage } from '@/lib/secure-page'

// 系统更新: 进入前要验证管理员密码. 一张整行卡片: 可更新的软件包(每页 10 行), 升级输出, 检查更新和全部升级(后台 apt-get upgrade, 运行中每 3 秒刷新).
interface Updates {
  supported: boolean
  packages: { package: string; version: string; current: string }[]
  listsAge: number | null
  running: boolean
  log: string
  lastExit: number | null
}

const { t, te } = useI18n()
const { state, guard } = useSecurePage()
const updates = ref<Updates>()
const busy = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

const errorText = (code: string) => (te(`vps.system.error.${code}`) ? t(`vps.system.error.${code}`) : undefined)

async function load() {
  clearTimeout(timer)
  const value = await guard(() => api<Updates>('system/updates'))
  if (!value) return
  updates.value = value
  state.value = 'ready'
  if (value.running) timer = setTimeout(load, 3000)
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

async function run(path: string) {
  busy.value = true
  const value = await guard(() => api<Updates>(path, { method: 'POST', body: {} }), errorText)
  busy.value = false
  if (!value) return
  updates.value = value
  if (value.running) timer = setTimeout(load, 3000)
}

const page = ref(1)
const columns = computed(() => [
  { key: 'package', label: t('vps.system.package'), mono: true },
  { key: 'current', label: t('vps.system.current'), mono: true },
  { key: 'version', label: t('vps.system.available'), mono: true },
])
const rows = computed(() => (updates.value?.packages ?? []).slice((page.value - 1) * 10, page.value * 10))
const note = computed(() => {
  const value = updates.value
  if (!value) return ''
  if (!value.supported) return t('vps.system.aptMissing')
  const age = value.listsAge == null ? '-' : value.listsAge < 3600 ? t('vps.system.minutesAgo', { n: Math.max(1, Math.round(value.listsAge / 60)) }) : t('vps.system.hoursAgo', { n: Math.round(value.listsAge / 3600) })
  return t('vps.system.updatesNote', { n: value.packages.length, age })
})
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('vps.system.updates')" :description="t('vps.system.updatesDescription')" />

    <PageSection v-if="state === 'loading'" :cols="4">
      <LoadingState />
    </PageSection>
    <AdminVerify v-else-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="load" />

    <PageSection v-else-if="updates" :cols="4" :title="t('vps.system.packages')" :description="note">
      <AlertBanner v-if="updates.running" tone="info" role="status">{{ t('vps.system.upgrading') }}</AlertBanner>
      <AlertBanner v-else-if="updates.lastExit != null && updates.lastExit !== 0" tone="destructive">{{ t('vps.system.upgradeFailed') }}</AlertBanner>
      <DataTable v-if="updates.supported" :columns="columns" :rows="rows" row-key="package" :caption="t('vps.system.packages')" :empty="t('vps.system.noUpdates')" />
      <PaginationBar v-if="updates.packages.length > 10" v-model="page" :total="updates.packages.length" />
      <LogOutput v-if="updates.log" :text="updates.log" :label="t('vps.system.upgradeLog')" />
      <FormActions v-if="updates.supported">
        <Button variant="outline" :disabled="busy || updates.running" @click="run('system/updates/check')"><RefreshCw aria-hidden="true" />{{ t('vps.system.check') }}</Button>
        <ConfirmDialog :title="t('vps.system.upgradeAll')" :description="t('vps.system.upgradeConfirm')" :confirm-label="t('vps.system.upgradeAll')" @confirm="run('system/updates/upgrade')">
          <template #trigger>
            <Button :disabled="busy || updates.running || !updates.packages.length"><PackageCheck aria-hidden="true" />{{ t('vps.system.upgradeAll') }}</Button>
          </template>
        </ConfirmDialog>
      </FormActions>
    </PageSection>
  </CardGrid>
</template>
