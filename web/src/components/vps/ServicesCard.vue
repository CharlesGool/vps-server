<script setup lang="ts">
import { RefreshCw } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/components/app/ActionMenu.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import SideDrawer from '@/components/app/SideDrawer.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import type { Guard } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 服务卡片(整行, 列表样式). 搜索和状态筛选在上, 表格在中间; 每行的操作菜单启动, 停止, 重启, 设置开机自启, 查看日志(侧边抽屉).
// 控制台自己的服务不能停止或取消自启(服务器也拒绝), 否则就再也打不开控制台.
interface Service { unit: string; load: string; active: string; sub: string; description: string; enabled: string }
type Action = 'start' | 'stop' | 'restart' | 'enable' | 'disable'

// 长列表一页 50 行(项目决策 2026-11-20)
const PAGE = 50
const { t, te } = useI18n()
const { guard } = defineProps<{ guard: Guard }>()
const rows = ref<Service[]>([])
const protectedUnits = ref<string[]>([])
const search = ref('')
const filter = ref<'all' | 'running' | 'failed'>('all')
const page = ref(1)
const busy = ref(false)
const pending = ref<{ unit: string; action: Action } | null>(null)
const log = ref<{ unit: string; text: string } | null>(null)
const logOpen = ref(false)

async function load() {
  busy.value = true
  const value = await guard(() => api<{ rows: Service[]; protected: string[] }>('system/services'))
  busy.value = false
  if (!value) return
  rows.value = value.rows
  protectedUnits.value = value.protected
}
onMounted(load)

const filters = computed(() => [
  { value: 'all' as const, label: t('vps.services.all') },
  { value: 'running' as const, label: t('vps.services.running') },
  { value: 'failed' as const, label: t('vps.services.failed') },
])
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return rows.value.filter(
    (row) =>
      (filter.value === 'all' || (filter.value === 'running' ? row.active === 'active' : row.active === 'failed')) &&
      (!query || `${row.unit} ${row.description}`.toLowerCase().includes(query)),
  )
})
watch([search, filter], () => (page.value = 1))
const pageRows = computed(() => filtered.value.slice((page.value - 1) * PAGE, page.value * PAGE))
const columns = computed(() => [
  { key: 'unit', label: t('vps.services.unit'), mono: true },
  { key: 'active', label: t('vps.services.state') },
  { key: 'enabled', label: t('vps.services.boot') },
  { key: 'description', label: t('vps.services.descriptionColumn') },
  { key: 'actions', label: t('vps.common.actions'), align: 'end' as const },
])
const tone = (row: Service) => (row.active === 'active' ? 'success' : row.active === 'failed' ? 'destructive' : 'neutral')
function menu(row: Service) {
  const own = protectedUnits.value.includes(row.unit)
  const items: { key: string; label: string; danger?: boolean }[] = [{ key: 'log', label: t('vps.services.log') }]
  if (row.active !== 'active') items.push({ key: 'start', label: t('vps.services.start') })
  if (row.enabled === 'disabled') items.push({ key: 'enable', label: t('vps.services.enable') })
  if (row.active === 'active') items.push({ key: 'restart', label: t('vps.services.restart'), danger: true })
  if (row.enabled === 'enabled' && !own) items.push({ key: 'disable', label: t('vps.services.disable'), danger: true })
  if (row.active === 'active' && !own) items.push({ key: 'stop', label: t('vps.services.stop'), danger: true })
  return items
}

async function choose(row: Service, key: string) {
  if (key === 'log') {
    const value = await guard(() => api<{ unit: string; text: string }>(`system/services/log?unit=${encodeURIComponent(row.unit)}`))
    if (value) {
      log.value = value
      logOpen.value = true
    }
    return
  }
  if (key === 'start' || key === 'enable') return run(row.unit, key)
  pending.value = { unit: row.unit, action: key as Action }
}

async function run(unit: string, action: Action) {
  busy.value = true
  const value = await guard(
    () => api<{ rows: Service[]; protected: string[] }>('system/services/action', { method: 'POST', body: { unit, action } }),
    (code) => (code === 'service_failed' ? t('vps.services.actionFailed', { unit }) : undefined),
  )
  busy.value = false
  if (value) {
    rows.value = value.rows
    showToast(t(`vps.services.done.${action}`, { unit }), 'success')
  }
}
function confirmPending() {
  const target = pending.value
  pending.value = null
  if (target) void run(target.unit, target.action)
}
// 确认对话框先关闭再发出 confirm: 关闭时先不清空要操作的对象, 等 confirm 处理完再清
function clearLater(clear: () => void) {
  setTimeout(clear)
}
</script>

<template>
  <PageSection :cols="4" :title="t('vps.services.heading', { n: rows.length })">
    <FormField v-slot="field" :label="t('vps.common.search')" :span="8">
      <Input :id="field.id" v-model="search" type="search" :placeholder="t('vps.services.searchHint')" />
    </FormField>
    <FormField :label="t('vps.services.show')" group :span="4">
      <SegmentedControl v-model="filter" :options="filters" :label="t('vps.services.show')" />
    </FormField>
    <DataTable long :columns="columns" :rows="pageRows" row-key="unit" :caption="t('vps.services.title')" :empty="t('vps.services.empty')">
      <template #cell-active="{ row }">
        <StatusBadge :tone="tone(row as unknown as Service)">{{ te(`vps.services.states.${row.active}`) ? t(`vps.services.states.${row.active}`) : String(row.active) }}</StatusBadge>
      </template>
      <template #cell-enabled="{ row }">{{ row.enabled ? (te(`vps.services.boots.${row.enabled}`) ? t(`vps.services.boots.${row.enabled}`) : String(row.enabled)) : '-' }}</template>
      <template #cell-actions="{ row }">
        <ActionMenu icon-only :label="t('vps.common.actionsFor', { name: String(row.unit) })" :items="menu(row as unknown as Service)" @select="choose(row as unknown as Service, $event)" />
      </template>
    </DataTable>
    <PaginationBar v-if="filtered.length > PAGE" v-model="page" :total="filtered.length" :page-size="PAGE" />
    <FormActions>
      <Button variant="outline" :disabled="busy" @click="load"><RefreshCw aria-hidden="true" />{{ t('vps.common.refresh') }}</Button>
    </FormActions>


  <ConfirmDialog
    :open="pending !== null"
    :title="pending ? t(`vps.services.confirm.${pending.action}`, { unit: pending.unit }) : ''"
    :description="pending ? t(`vps.services.consequence.${pending.action}`) : ''"
    :confirm-label="pending ? t(`vps.services.${pending.action}`) : ''"
    danger
    @confirm="confirmPending"
    @update:open="(open: boolean) => { if (!open) clearLater(() => (pending = null)) }"
  />

  <SideDrawer v-model:open="logOpen" :title="log?.unit ?? ''" :description="t('vps.services.logHelp')">
    <LogOutput :text="log?.text ?? ''" :label="t('vps.services.log')" :empty="t('vps.services.logEmpty')" />
  </SideDrawer>
  </PageSection>
</template>
