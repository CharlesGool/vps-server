<script setup lang="ts">
import { RefreshCw } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/components/app/ActionMenu.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { formatBytes } from '@/lib/format'
import type { Guard } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 进程卡片(整行, 列表样式). 上面搜索和排序, 中间表格(每页 10 行), 每行的操作菜单可以结束或强制结束进程(都要确认).
interface Process { pid: number; ppid: number; name: string; state: string; user: string; cpu: number; memory: number; command: string }

const { t } = useI18n()
const { guard } = defineProps<{ guard: Guard }>()
const rows = ref<Process[]>([])
const self = ref(0)
const search = ref('')
const sort = ref<'cpu' | 'memory' | 'pid'>('cpu')
const page = ref(1)
const busy = ref(false)
const pending = ref<{ pid: number; name: string; force: boolean } | null>(null)

async function load() {
  busy.value = true
  const value = await guard(() => api<{ rows: Process[]; self: number }>('system/processes'))
  busy.value = false
  if (!value) return
  rows.value = value.rows
  self.value = value.self
}
onMounted(load)

const sorts = computed(() => [
  { value: 'cpu' as const, label: t('vps.processes.byCpu') },
  { value: 'memory' as const, label: t('vps.processes.byMemory') },
  { value: 'pid' as const, label: 'PID' },
])
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  const list = query
    ? rows.value.filter((row) => `${row.pid} ${row.name} ${row.user} ${row.command}`.toLowerCase().includes(query))
    : rows.value
  return [...list].sort((a, b) => (sort.value === 'pid' ? a.pid - b.pid : (b[sort.value] as number) - (a[sort.value] as number)))
})
watch([search, sort], () => (page.value = 1))
const pageRows = computed(() =>
  filtered.value.slice((page.value - 1) * 10, page.value * 10).map((row) => ({ ...row, cpuText: `${row.cpu.toFixed(1)}%`, memoryText: formatBytes(row.memory) })),
)
const columns = computed(() => [
  { key: 'pid', label: 'PID', align: 'end' as const, mono: true },
  { key: 'name', label: t('vps.processes.name'), mono: true },
  { key: 'user', label: t('vps.processes.user') },
  { key: 'cpuText', label: 'CPU', align: 'end' as const, mono: true },
  { key: 'memoryText', label: t('vps.processes.memory'), align: 'end' as const, mono: true },
  { key: 'command', label: t('vps.processes.command'), mono: true },
  { key: 'actions', label: t('vps.common.actions'), align: 'end' as const },
])
const menu = computed(() => [
  { key: 'term', label: t('vps.processes.terminate'), danger: true },
  { key: 'kill', label: t('vps.processes.kill'), danger: true },
])
function choose(row: Process, key: string) {
  pending.value = { pid: row.pid, name: row.name, force: key === 'kill' }
}
async function confirmKill() {
  const target = pending.value
  pending.value = null
  if (!target) return
  const done = await guard(
    // 成功时服务器不返回内容(204), 换成 true 以便和失败(undefined)区分
    () => api('system/processes/kill', { method: 'POST', body: { pid: target.pid, force: target.force } }).then(() => true),
    (code) => (code === 'not_found' ? t('vps.processes.gone') : undefined),
  )
  if (done !== undefined) showToast(t('vps.processes.signalled', { pid: target.pid }), 'success')
  await load()
}
</script>

<template>
  <PageSection :cols="4" :title="t('vps.processes.heading', { n: rows.length })">
    <FormField v-slot="field" :label="t('vps.common.search')" :span="8">
      <Input :id="field.id" v-model="search" type="search" :placeholder="t('vps.processes.searchHint')" />
    </FormField>
    <FormField :label="t('vps.processes.sort')" group :span="4">
      <SegmentedControl v-model="sort" :options="sorts" :label="t('vps.processes.sort')" />
    </FormField>
    <DataTable :columns="columns" :rows="pageRows" row-key="pid" :caption="t('vps.processes.title')" :empty="t('vps.processes.empty')">
      <template #cell-command="{ row }">{{ String(row.command).slice(0, 120) }}</template>
      <template #cell-actions="{ row }">
        <ActionMenu
          v-if="Number(row.pid) > 1 && Number(row.pid) !== self"
          icon-only
          :label="t('vps.common.actionsFor', { name: `${row.name} (${row.pid})` })"
          :items="menu"
          @select="choose(row as unknown as Process, $event)"
        />
      </template>
    </DataTable>
    <PaginationBar v-if="filtered.length > 10" v-model="page" :total="filtered.length" />
    <FormActions>
      <Button variant="outline" :disabled="busy" @click="load"><RefreshCw aria-hidden="true" />{{ t('vps.common.refresh') }}</Button>
    </FormActions>


  <ConfirmDialog
    :open="pending !== null"
    :title="pending?.force ? t('vps.processes.kill') : t('vps.processes.terminate')"
    :description="t(pending?.force ? 'vps.processes.killConfirm' : 'vps.processes.terminateConfirm', { name: pending?.name ?? '', pid: pending?.pid ?? 0 })"
    :confirm-label="pending?.force ? t('vps.processes.kill') : t('vps.processes.terminate')"
    danger
    @confirm="confirmKill"
    @update:open="(open: boolean) => { if (!open) pending = null }"
  />
  </PageSection>
</template>
