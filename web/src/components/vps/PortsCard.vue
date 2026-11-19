<script setup lang="ts">
import { RefreshCw } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import type { Guard } from '@/lib/secure-page'

// vps-server 项目组件: 监听端口卡片(整行, 列表样式). 哪个程序在哪个地址和端口监听, 以及端口登记(PORTS.md)里记下的用途.
interface Port { protocol: string; address: string; port: number; process: string; pid: number | null; owner: string }

// 长列表一页 50 行(项目决策 2026-11-20)
const PAGE = 50
const { t } = useI18n()
const { guard } = defineProps<{ guard: Guard }>()
const rows = ref<Port[]>([])
const search = ref('')
const protocol = ref<'all' | 'tcp' | 'udp'>('all')
const page = ref(1)
const busy = ref(false)

async function load() {
  busy.value = true
  const value = await guard(() => api<{ rows: Port[] }>('system/ports'))
  busy.value = false
  if (!value) return
  rows.value = value.rows
}
onMounted(load)

const protocols = computed(() => [
  { value: 'all' as const, label: t('vps.ports.all') },
  { value: 'tcp' as const, label: 'TCP' },
  { value: 'udp' as const, label: 'UDP' },
])
const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  return rows.value.filter(
    (row) =>
      (protocol.value === 'all' || row.protocol === protocol.value) &&
      (!query || `${row.port} ${row.address} ${row.process} ${row.owner}`.toLowerCase().includes(query)),
  )
})
watch([search, protocol], () => (page.value = 1))
const pageRows = computed(() =>
  filtered.value.slice((page.value - 1) * PAGE, page.value * PAGE).map((row) => ({
    ...row,
    key: `${row.protocol}-${row.address}-${row.port}`,
    protocolText: row.protocol.toUpperCase(),
    processText: row.process ? `${row.process}${row.pid ? ` (${row.pid})` : ''}` : '',
  })),
)
const columns = computed(() => [
  { key: 'protocolText', label: t('vps.ports.protocol') },
  { key: 'address', label: t('vps.ports.address'), mono: true },
  { key: 'port', label: t('vps.ports.port'), align: 'end' as const, mono: true },
  { key: 'processText', label: t('vps.ports.process'), mono: true },
  { key: 'owner', label: t('vps.ports.owner') },
])
</script>

<template>
  <PageSection :cols="4" :title="t('vps.ports.heading', { n: rows.length })">
    <FormField v-slot="field" :label="t('vps.common.search')" :span="8">
      <Input :id="field.id" v-model="search" type="search" :placeholder="t('vps.ports.searchHint')" />
    </FormField>
    <FormField :label="t('vps.ports.protocol')" group :span="4">
      <SegmentedControl v-model="protocol" :options="protocols" :label="t('vps.ports.protocol')" />
    </FormField>
    <DataTable long :columns="columns" :rows="pageRows" row-key="key" :caption="t('vps.ports.title')" :empty="t('vps.ports.empty')" />
    <PaginationBar v-if="filtered.length > PAGE" v-model="page" :total="filtered.length" :page-size="PAGE" />
    <FormActions>
      <Button variant="outline" :disabled="busy" @click="load"><RefreshCw aria-hidden="true" />{{ t('vps.common.refresh') }}</Button>
    </FormActions>
  </PageSection>
</template>
