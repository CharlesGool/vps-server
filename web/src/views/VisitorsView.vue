<script setup lang="ts">
import { Eraser } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// 最近访问者: 一张整行卡片, 上方筛选(全部/仅入站/仅外部)和清除历史, 下面是分页的表格(每页 10 行).
type Visitor = {
  ip: string
  scope: 'loopback' | 'private' | 'public'
  direction: 'in' | 'out'
  firstSeen: string
  lastSeen: string
  hits: number
  ports: string
  lastRequest: string
}

const { t } = useI18n()
const data = ref<{ max: number; rows: Visitor[] }>()
const filter = ref<'all' | 'inbound' | 'public'>('all')
const page = ref(1)
const busy = ref(false)

async function load() {
  try {
    data.value = await api<{ max: number; rows: Visitor[] }>('visitors')
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)

const filters = computed(() => [
  { value: 'all' as const, label: t('legacy.show_all') },
  { value: 'inbound' as const, label: t('legacy.show_inbound') },
  { value: 'public' as const, label: t('legacy.show_external') },
])
const shown = computed(() =>
  (data.value?.rows ?? []).filter((row) => filter.value === 'all' || (filter.value === 'inbound' ? row.direction === 'in' : row.scope === 'public')),
)
watch(filter, () => (page.value = 1))
const pageRows = computed(() => shown.value.slice((page.value - 1) * 10, page.value * 10))
const columns = computed(() => [
  { key: 'ip', label: t('legacy.col_ip'), mono: true },
  { key: 'direction', label: t('legacy.col_dir') },
  { key: 'firstSeen', label: t('legacy.col_first'), mono: true },
  { key: 'lastSeen', label: t('legacy.col_last'), mono: true },
  { key: 'hits', label: t('legacy.col_hits'), align: 'end' as const, mono: true },
  { key: 'ports', label: t('legacy.col_ports'), align: 'end' as const, mono: true },
  { key: 'lastRequest', label: t('legacy.col_lastreq'), mono: true },
])
const title = computed(() => t('legacy.visitors_heading', { n: data.value?.rows.length ?? 0, max: data.value?.max ?? 0 }))

async function clear() {
  busy.value = true
  try {
    await api('visitors/clear', { method: 'POST', body: {} })
    showToast(t('legacy.visitors_clear_done'), 'success')
    await load()
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('legacy.visitors_clear_failed'), 'destructive')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('legacy.visitors')" :description="t('vps.visitors.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <PageSection v-else :cols="4" :title="title">
      <FormField :label="t('vps.visitors.filter')" group>
        <SegmentedControl v-model="filter" :options="filters" :label="t('vps.visitors.filter')" />
      </FormField>
      <DataTable :columns="columns" :rows="pageRows" row-key="ip" :caption="title" :empty="t('legacy.no_visits')">
        <template #cell-ip="{ row }">
          {{ row.ip }}
          <StatusBadge v-if="row.scope !== 'public'">{{ t(`legacy.scope_${row.scope}`) }}</StatusBadge>
        </template>
        <template #cell-direction="{ row }">
          <StatusBadge :tone="row.direction === 'in' ? 'info' : 'neutral'">{{ t(`legacy.dir_${row.direction}`) }}</StatusBadge>
        </template>
        <template #cell-ports="{ row }">{{ row.ports || '—' }}</template>
        <template #cell-lastRequest="{ row }">{{ row.lastRequest || '—' }}</template>
      </DataTable>
      <PaginationBar v-if="shown.length > 10" v-model="page" :total="shown.length" />
      <FormActions>
        <ConfirmDialog
          :title="t('legacy.visitors_clear')"
          :description="t('legacy.visitors_clear_confirm')"
          :confirm-label="t('legacy.visitors_clear')"
          danger
          @confirm="clear"
        >
          <template #trigger>
            <Button variant="destructive" :disabled="busy || !data.rows.length"><Eraser aria-hidden="true" />{{ t('legacy.visitors_clear') }}</Button>
          </template>
        </ConfirmDialog>
      </FormActions>
    </PageSection>
  </CardGrid>
</template>
