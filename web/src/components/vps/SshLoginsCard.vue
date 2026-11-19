<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import DataTable from '@/components/app/DataTable.vue'
import FormField from '@/components/app/FormField.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 最近访问页的 SSH 登录记录(整行, 列表样式). 最近 7 天, 分成功, 失败和失败最多的来源地址三种显示, 每页 10 行.
interface Ssh {
  accepted: { time: string; method: string; user: string; ip: string }[]
  failed: { time: string; user: string; ip: string }[]
  failedTotal: number
  topFailed: { ip: string; count: number }[]
}

const { t } = useI18n()
const ssh = ref<Ssh>()
onMounted(async () => {
  try {
    ssh.value = await api<Ssh>('visitors/ssh')
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
})

const view = ref<'accepted' | 'failed' | 'top'>('accepted')
const page = ref(1)
watch(view, () => (page.value = 1))
const views = computed(() => [
  { value: 'accepted' as const, label: t('vps.system.sshAccepted') },
  { value: 'failed' as const, label: t('vps.system.sshFailed') },
  { value: 'top' as const, label: t('vps.system.sshTop') },
])
const all = computed<Record<string, unknown>[]>(() => {
  const value = ssh.value
  if (!value) return []
  if (view.value === 'top') return value.topFailed.map((row) => ({ key: row.ip, ip: row.ip, count: row.count }))
  return (view.value === 'accepted' ? value.accepted : value.failed).map((row, index) => ({ key: `${index}`, ...row }))
})
const rows = computed(() => all.value.slice((page.value - 1) * 10, page.value * 10))
const columns = computed(() =>
  view.value === 'top'
    ? [
        { key: 'ip', label: t('vps.system.ip'), mono: true },
        { key: 'count', label: t('vps.system.failures'), align: 'end' as const, mono: true },
      ]
    : [
        { key: 'time', label: t('vps.system.time'), mono: true },
        { key: 'user', label: t('vps.system.user'), mono: true },
        { key: 'ip', label: t('vps.system.ip'), mono: true },
        ...(view.value === 'accepted' ? [{ key: 'method', label: t('vps.system.method') }] : []),
      ],
)
</script>

<template>
  <PageSection :cols="4" :title="t('vps.system.ssh')" :description="ssh ? t('vps.system.sshNote', { n: ssh.failedTotal }) : undefined">
    <FormField :label="t('vps.system.sshShow')" group>
      <SegmentedControl v-model="view" :options="views" :label="t('vps.system.sshShow')" />
    </FormField>
    <DataTable :columns="columns" :rows="rows" row-key="key" :caption="t('vps.system.ssh')" :empty="t('vps.system.sshEmpty')" />
    <PaginationBar v-if="all.length > 10" v-model="page" :total="all.length" />
  </PageSection>
</template>
