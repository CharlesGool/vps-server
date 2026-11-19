<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import CardGrid from '@/components/app/CardGrid.vue'
import DataTable from '@/components/app/DataTable.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { api, isSignedOut } from '@/lib/api'

// 一个转发域名的访问日志: Caddy 记录的最近 200 条请求, 新的在前, 每页 10 条.
type Row = { id: number; time: string; client: string; method: string; path: string; status: number | null; duration: string }
const { t } = useI18n()
const route = useRoute()
const host = computed(() => (typeof route.query.host === 'string' ? route.query.host : ''))
const rows = ref<Row[]>()
const missing = ref(false)
const page = ref(1)

onMounted(async () => {
  if (!host.value) {
    missing.value = true
    return
  }
  try {
    rows.value = (await api<{ rows: Row[] }>(`domains/log?host=${encodeURIComponent(host.value)}`)).rows
  } catch (err) {
    if (!isSignedOut(err)) missing.value = true
  }
})
const pageRows = computed(() => (rows.value ?? []).slice((page.value - 1) * 10, page.value * 10))
const columns = computed(() => [
  { key: 'time', label: t('console.domains_log_time'), mono: true },
  { key: 'client', label: t('console.domains_log_client'), mono: true },
  { key: 'method', label: t('console.domains_log_method') },
  { key: 'path', label: t('console.domains_log_path'), mono: true },
  { key: 'status', label: t('console.domains_log_status'), align: 'end' as const, mono: true },
  { key: 'duration', label: t('console.domains_log_duration'), align: 'end' as const, mono: true },
])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.domains_access_log')" :description="host || undefined" :trail="[{ to: '/domains', label: t('console.domains') }]" />
    <PageSection v-if="!rows && !missing" :cols="4">
      <LoadingState />
    </PageSection>
    <PageSection v-else :cols="4" :title="host || t('console.domains_access_log')" :description="t('console.domains_log_note')">
      <DataTable :columns="columns" :rows="pageRows" row-key="id" :caption="t('console.domains_access_log')" :empty="t('console.domains_log_empty')">
        <template #cell-status="{ row }">
          <StatusBadge v-if="row.status !== null" :tone="row.status >= 400 ? 'destructive' : 'success'">{{ row.status }}</StatusBadge>
        </template>
      </DataTable>
      <PaginationBar v-if="(rows?.length ?? 0) > 10" v-model="page" :total="rows?.length ?? 0" />
    </PageSection>
  </CardGrid>
</template>
