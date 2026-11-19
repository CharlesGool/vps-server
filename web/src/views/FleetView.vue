<script setup lang="ts">
import { Plus, RefreshCw, ServerCog } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import ApiTokensCard from '@/components/vps/ApiTokensCard.vue'
import { api } from '@/lib/api'
import { formatBytes } from '@/lib/format'
import type { Monitor } from '@/lib/monitor'
import { useSecurePage } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// 集中管理: 两件事放在一页. 上面是这台主机管理的其他主机(列表, 一张整行卡片), 下面是让别人管理这台主机的 API 令牌(ApiTokensCard).
// 主机列表: 每台主机一行: 状态, 版本, CPU, 内存, 硬盘, 本周期流量; 可多选后批量升级或备份.
// 添加主机分两步(对话框): 先填地址读出证书指纹核对, 再填对方安全设置里生成的 API 令牌. 每 30 秒刷新一次.
interface Host {
  id: string
  name: string
  url: string
  mode: 'ca' | 'pin'
  fingerprint: string
  ok: boolean
  error?: string
  checked?: number
  status?: {
    hostname: string
    version: string
    serverLabel: string
    resources: Pick<Monitor, 'cpu' | 'memory' | 'disk' | 'load' | 'uptime'>
    traffic: { used: number; cap: number | null } | null
    failed: string[]
  }
}

// 长列表一页 50 行(项目决策 2026-11-20)
const PAGE = 50
const { t, te } = useI18n()
const { state, guard } = useSecurePage()
const hosts = ref<Host[]>([])
const selected = ref<unknown[]>([])
const page = ref(1)
const busy = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

const errorText = (code: string) => {
  const key = `vps.fleet.error.${code}`
  return te(key) ? t(key) : undefined
}

async function load(refresh = false) {
  clearTimeout(timer)
  busy.value = refresh
  const value = await guard(() => api<{ hosts: Host[] }>(`fleet${refresh ? '?refresh=1' : ''}`))
  busy.value = false
  if (value) {
    hosts.value = value.hosts
    state.value = 'ready'
    timer = setTimeout(() => load(), 30000)
  }
}
onMounted(() => load())
onBeforeUnmount(() => clearTimeout(timer))

const percent = (used: number, total: number) => (total ? Math.round((used * 1000) / total) / 10 : 0)
const pageRows = computed(() =>
  hosts.value.slice((page.value - 1) * PAGE, page.value * PAGE).map((host) => {
    const resources = host.status?.resources
    return {
      ...host,
      label: host.status?.serverLabel || host.name,
      version: host.status?.version ?? '',
      cpu: resources ? resources.cpu.percent : null,
      memory: resources ? percent(resources.memory.used, resources.memory.total) : null,
      disk: resources?.disk ? resources.disk.percent : null,
      traffic: host.status?.traffic ? formatBytes(host.status.traffic.used) : '',
    }
  }),
)
const columns = computed(() => [
  { key: 'label', label: t('vps.fleet.host') },
  { key: 'ok', label: t('vps.fleet.state') },
  { key: 'version', label: t('vps.fleet.version'), mono: true },
  { key: 'cpu', label: 'CPU', align: 'end' as const, mono: true },
  { key: 'memory', label: t('vps.monitor.memory'), align: 'end' as const, mono: true },
  { key: 'disk', label: t('vps.monitor.disk'), align: 'end' as const, mono: true },
  { key: 'traffic', label: t('vps.fleet.traffic'), align: 'end' as const, mono: true },
  { key: 'actions', label: t('vps.common.actions'), align: 'end' as const },
])
const menu = computed(() => [
  { key: 'open', label: t('vps.fleet.openConsole') },
  { key: 'details', label: t('vps.fleet.details') },
  { key: 'remove', label: t('vps.fleet.remove'), danger: true },
])
const details = ref<Host | null>(null)
const detailsOpen = computed({ get: () => details.value !== null, set: (value) => { if (!value) details.value = null } })
const removing = ref<Host | null>(null)
function choose(host: Host, key: string) {
  if (key === 'open') window.open(host.url, '_blank', 'noopener')
  else if (key === 'details') details.value = host
  else removing.value = host
}
const detailItems = computed(() => {
  const host = details.value
  if (!host) return []
  return [
    { key: 'url', label: t('vps.fleet.url'), value: host.url, mono: true, copyable: true },
    { key: 'hostname', label: t('vps.fleet.hostname'), value: host.status?.hostname, mono: true },
    { key: 'check', label: t('vps.fleet.certCheck'), value: t(`vps.fleet.mode.${host.mode}`) },
    { key: 'fingerprint', label: t('vps.fleet.fingerprint'), value: host.fingerprint, mono: true },
    { key: 'failed', label: t('vps.fleet.failedUnits'), value: host.status?.failed.join(', ') || undefined, mono: true },
    { key: 'error', label: t('vps.fleet.error.title'), value: host.ok ? undefined : errorText(host.error ?? '') ?? host.error },
  ]
})

async function remove() {
  const host = removing.value
  removing.value = null
  if (!host) return
  const value = await guard(() => api<{ hosts: Host[] }>('fleet/delete', { method: 'POST', body: { id: host.id } }), errorText)
  if (value) {
    hosts.value = value.hosts
    showToast(t('vps.fleet.removed', { name: host.name }), 'success')
  }
}

// 批量操作
const batch = ref<'upgrade' | 'backup' | null>(null)
const results = ref<{ name: string; ok: boolean; error?: string }[]>([])
async function runBatch() {
  const action = batch.value
  batch.value = null
  if (!action) return
  busy.value = true
  const value = await guard(() => api<{ results: Record<string, { ok: boolean; error?: string }> }>('fleet/action', { method: 'POST', body: { ids: selected.value, action } }), errorText)
  busy.value = false
  if (!value) return
  results.value = Object.entries(value.results).map(([id, result]) => ({ name: hosts.value.find((host) => host.id === id)?.name ?? id, ...result }))
  showToast(t(`vps.fleet.batchStarted.${action}`, { n: results.value.filter((row) => row.ok).length }), 'success')
}
const failedResults = computed(() => results.value.filter((row) => !row.ok))

// 添加主机
const addOpen = ref(false)
const add = ref({ name: '', url: 'https://', token: '', mode: '' as '' | 'ca' | 'pin', fingerprint: '' })
const addError = ref('')
function openAdd() {
  add.value = { name: '', url: 'https://', token: '', mode: '', fingerprint: '' }
  addError.value = ''
  addOpen.value = true
}
async function probe() {
  addError.value = ''
  busy.value = true
  const value = await guard(() => api<{ mode: 'ca' | 'pin'; fingerprint: string }>('fleet/probe', { method: 'POST', body: { url: add.value.url } }), (code) => {
    addError.value = errorText(code) ?? t('vps.common.failed')
    return addError.value
  })
  busy.value = false
  if (value) Object.assign(add.value, value)
}
async function save() {
  addError.value = ''
  busy.value = true
  const value = await guard(() => api<{ hosts: Host[] }>('fleet/add', { method: 'POST', body: add.value }), (code) => {
    addError.value = errorText(code) ?? t('vps.common.failed')
    return addError.value
  })
  busy.value = false
  if (value) {
    hosts.value = value.hosts
    addOpen.value = false
    showToast(t('vps.fleet.added', { name: add.value.name }), 'success')
  }
}
// 确认对话框先关闭再发出 confirm: 关闭时先不清空要操作的对象, 等 confirm 处理完再清
function clearLater(clear: () => void) {
  setTimeout(clear)
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('vps.fleet.title')" :description="t('vps.fleet.description')" />

    <PageSection v-if="state === 'loading'" :cols="4">
      <LoadingState />
    </PageSection>
    <AdminVerify v-else-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="load()" />

    <PageSection v-else-if="!hosts.length" :cols="4">
      <EmptyState :icon="ServerCog" :title="t('vps.fleet.emptyTitle')" :description="t('vps.fleet.emptyHelp')" />
      <FormActions>
        <Button @click="openAdd"><Plus aria-hidden="true" />{{ t('vps.fleet.add') }}</Button>
      </FormActions>
    </PageSection>

    <PageSection v-else :cols="4" :title="t('vps.fleet.heading', { n: hosts.length })" :description="t('vps.fleet.refreshNote')">
      <AlertBanner v-if="failedResults.length" tone="destructive">
        {{ t('vps.fleet.batchFailed', { names: failedResults.map((row) => `${row.name} (${errorText(row.error ?? '') ?? row.error})`).join(', ') }) }}
      </AlertBanner>
      <DataTable long v-model:selected="selected" selectable :columns="columns" :rows="pageRows" row-key="id" :caption="t('vps.fleet.title')" :empty="t('vps.fleet.emptyTitle')">
        <template #cell-ok="{ row }">
          <StatusBadge :tone="row.ok ? ((row as unknown as Host).status?.failed.length ? 'warning' : 'success') : 'destructive'">
            {{ row.ok ? ((row as unknown as Host).status?.failed.length ? t('vps.fleet.degraded') : t('vps.fleet.online')) : t('vps.fleet.offline') }}
          </StatusBadge>
        </template>
        <template #cell-cpu="{ row }">
          <ProgressBar v-if="row.cpu != null" variant="inline" :label="`${row.label} CPU`" :value="Number(row.cpu)" :text="`${Number(row.cpu).toFixed(1)}%`" />
          <template v-else>-</template>
        </template>
        <template #cell-memory="{ row }">
          <ProgressBar v-if="row.memory != null" variant="inline" :label="`${row.label} ${t('vps.monitor.memory')}`" :value="Number(row.memory)" :text="`${Number(row.memory).toFixed(1)}%`" />
          <template v-else>-</template>
        </template>
        <template #cell-disk="{ row }">
          <ProgressBar v-if="row.disk != null" variant="inline" :label="`${row.label} ${t('vps.monitor.disk')}`" :value="Number(row.disk)" :text="`${Number(row.disk).toFixed(1)}%`" />
          <template v-else>-</template>
        </template>
        <template #cell-actions="{ row }">
          <ActionMenu icon-only :label="t('vps.common.actionsFor', { name: String(row.label) })" :items="menu" @select="choose(row as unknown as Host, $event)" />
        </template>
      </DataTable>
      <PaginationBar v-if="hosts.length > PAGE" v-model="page" :total="hosts.length" :page-size="PAGE" />
      <FormActions>
        <Button variant="outline" :disabled="busy" @click="load(true)"><RefreshCw aria-hidden="true" />{{ t('vps.common.refresh') }}</Button>
        <Button variant="outline" :disabled="busy || !selected.length" @click="batch = 'backup'">{{ t('vps.fleet.backupSelected', { n: selected.length }) }}</Button>
        <Button variant="outline" :disabled="busy || !selected.length" @click="batch = 'upgrade'">{{ t('vps.fleet.upgradeSelected', { n: selected.length }) }}</Button>
        <Button :disabled="busy" @click="openAdd"><Plus aria-hidden="true" />{{ t('vps.fleet.add') }}</Button>
      </FormActions>
    </PageSection>

    <ApiTokensCard v-if="state === 'ready'" @expired="state = 'verify'" />

    <ConfirmDialog
      :open="batch !== null"
      :title="batch ? t(`vps.fleet.batch.${batch}`, { n: selected.length }) : ''"
      :description="batch ? t(`vps.fleet.batchConfirm.${batch}`) : ''"
      :confirm-label="batch ? t(`vps.fleet.batch.${batch}`, { n: selected.length }) : ''"
      @confirm="runBatch"
      @update:open="(open: boolean) => { if (!open) clearLater(() => (batch = null)) }"
    />
    <ConfirmDialog
      :open="removing !== null"
      :title="t('vps.fleet.remove')"
      :description="t('vps.fleet.removeConfirm', { name: removing?.name ?? '' })"
      :confirm-label="t('vps.fleet.remove')"
      danger
      @confirm="remove"
      @update:open="(open: boolean) => { if (!open) clearLater(() => (removing = null)) }"
    />

    <AppDialog v-model:open="detailsOpen" :title="details?.name ?? ''">
      <DescriptionList :items="detailItems" />
    </AppDialog>

    <AppDialog v-model:open="addOpen" :title="t('vps.fleet.add')" :description="t('vps.fleet.addHelp')">
      <FormField v-slot="urlField" :label="t('vps.fleet.url')">
        <Input :id="urlField.id" v-model.trim="add.url" spellcheck="false" autocomplete="off" :disabled="!!add.mode" />
      </FormField>
      <template v-if="add.mode">
        <AlertBanner :tone="add.mode === 'ca' ? 'success' : 'warning'">{{ t(`vps.fleet.probe.${add.mode}`) }}</AlertBanner>
        <DescriptionList :items="[{ key: 'fp', label: t('vps.fleet.fingerprint'), value: add.fingerprint, mono: true }]" />
        <FormField v-slot="fld" :label="t('vps.fleet.name')">
          <Input :id="fld.id" v-model.trim="add.name" maxlength="40" autocomplete="off" />
        </FormField>
        <FormField v-slot="fld" :label="t('vps.fleet.token')" :help="t('vps.fleet.tokenHelp')">
          <PasswordInput :id="fld.id" v-model="add.token" autocomplete="off" />
        </FormField>
      </template>
      <AlertBanner v-if="addError" tone="destructive">{{ addError }}</AlertBanner>
      <template #footer>
        <Button variant="outline" type="button" @click="addOpen = false">{{ t('component.cancel') }}</Button>
        <Button v-if="!add.mode" type="button" :disabled="busy || !add.url.startsWith('https://')" @click="probe">{{ t('vps.fleet.next') }}</Button>
        <Button v-else type="button" :disabled="busy || !add.name || !add.token" @click="save"><Plus aria-hidden="true" />{{ t('vps.fleet.add') }}</Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
