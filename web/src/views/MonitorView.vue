<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import DataTable from '@/components/app/DataTable.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import StatCard from '@/components/app/StatCard.vue'
import TrendChart from '@/components/app/TrendChart.vue'
import MonitorAlertsCards from '@/components/vps/MonitorAlertsCards.vue'
import { api, isSignedOut } from '@/lib/api'
import { formatBytes } from '@/lib/format'
import { formatDuration, formatRate, gpuCards, gpuName, hourLabel, secondLabel, type HistoryRow, type Monitor } from '@/lib/monitor'

// 资源监控: 仪表板模式. 一行 4 张数据卡(CPU, 内存, 硬盘, 负载), 整行的实时图和 24 小时趋势图, 磁盘表, 主机信息, 网卡表.
// 每 5 秒刷新一次; 最下面是资源告警的开关和阈值.
const { t, locale } = useI18n()
const data = ref<Monitor>()
let timer: ReturnType<typeof setTimeout> | undefined

async function load() {
  clearTimeout(timer)
  try {
    data.value = await api<Monitor>('monitor')
  } catch (err) {
    if (isSignedOut(err)) return
  }
  timer = setTimeout(load, 5000)
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

const percent = (used: number, total: number) => (total ? Math.round((used * 1000) / total) / 10 : 0)
const memoryPercent = computed(() => (data.value ? percent(data.value.memory.used, data.value.memory.total) : 0))
const trend = (column: 1 | 2) => (data.value?.recent ?? []).map((row) => row[column]).filter((value): value is number => value != null)

const cards = computed(() => {
  const value = data.value
  if (!value) return []
  const ago = value.hourAgo
  const load = value.load
  return [
    { key: 'cpu', label: t('vps.monitor.cpu'), value: `${value.cpu.percent.toFixed(1)}%`,
      delta: ago ? Math.round((value.cpu.percent - ago.cpu) * 10) / 10 : 0, deltaLabel: t('vps.monitor.vsHourAgo'), trend: trend(1) },
    { key: 'memory', label: t('vps.monitor.memory'), value: `${memoryPercent.value.toFixed(1)}%`,
      delta: ago ? Math.round((memoryPercent.value - ago.memory) * 10) / 10 : 0, deltaLabel: t('vps.monitor.vsHourAgo'), trend: trend(2) },
    { key: 'disk', label: t('vps.monitor.disk'), value: value.disk ? `${value.disk.percent.toFixed(1)}%` : '-',
      delta: 0, deltaLabel: value.disk ? t('vps.monitor.diskFree', { free: formatBytes(value.disk.free) }) : '-', trend: undefined },
    { key: 'load', label: t('vps.monitor.load'), value: load[0].toFixed(2),
      delta: load[2] ? Math.round(((load[0] - load[2]) / load[2]) * 100) : 0, deltaLabel: t('vps.monitor.vsLoad15'), trend: undefined },
    ...gpuCards(value.gpus, t, value.gpus.map((_, index) => recentGpu.value.map((row) => row[1]![index]?.[0] ?? 0))),
  ]
})

// 两组图: 实时(最近 1 分钟, 每 5 秒一个点)和最近 15 分钟(每分钟的平均值, 15 个点; 用户要求 15 分钟, 比模板建议的横轴 12 项多 3 项,
// 放不下的横轴文字由 TrendChart 隔项显示). 只画有数据的分钟, 刚启动时只有最近几分钟. 卡片里的小折线也是这 15 分钟.
const live = computed(() => data.value?.live ?? [])
const day = computed(() => (data.value?.recent ?? []).filter((row) => row[1] != null))
const usage = (rows: HistoryRow[]) => [
  { name: t('vps.monitor.cpu'), values: rows.map((row) => row[1] ?? 0) },
  { name: t('vps.monitor.memory'), values: rows.map((row) => row[2] ?? 0) },
]
const traffic = (rows: HistoryRow[]) => [
  { name: t('vps.monitor.download'), values: rows.map((row) => row[3] ?? 0) },
  { name: t('vps.monitor.upload'), values: rows.map((row) => row[4] ?? 0) },
]
const liveLabels = computed(() => live.value.map((row) => secondLabel(row[0], locale.value)))
const dayLabels = computed(() => day.value.map((row) => hourLabel(row[0], locale.value)))
const percentText = (value: number) => `${value.toFixed(1)}%`

// GPU 图: 每张卡一条使用率线; 不超过 2 张卡时再加显存线(图表最多 4 条)
const liveGpu = computed(() => data.value?.gpuLive ?? [])
const recentGpu = computed(() => (data.value?.gpuRecent ?? []).filter((row): row is [number, number[][]] => row[1] != null))
function gpuSeries(rows: [number, number[][]][]) {
  const gpus = data.value?.gpus ?? []
  const series = gpus.slice(0, 4).map((gpu, index) => ({ name: t('vps.monitor.gpuUtil', { name: gpuName(gpu.name) }), values: rows.map((row) => row[1][index]?.[0] ?? 0) }))
  if (gpus.length <= 2) {
    series.push(...gpus.map((gpu, index) => ({ name: t('vps.monitor.gpuMem', { name: gpuName(gpu.name) }), values: rows.map((row) => row[1][index]?.[1] ?? 0) })))
  }
  return series
}
const liveGpuLabels = computed(() => liveGpu.value.map((row) => secondLabel(row[0], locale.value)))
const recentGpuLabels = computed(() => recentGpu.value.map((row) => hourLabel(row[0], locale.value)))

const diskColumns = computed(() => [
  { key: 'mount', label: t('vps.monitor.mount'), mono: true },
  { key: 'type', label: t('vps.monitor.fsType') },
  { key: 'size', label: t('vps.monitor.size'), align: 'end' as const, mono: true },
  { key: 'usage', label: t('vps.monitor.used'), align: 'end' as const, mono: true },
])
const diskPage = ref(1)
const diskRows = computed(() =>
  (data.value?.disks ?? []).slice((diskPage.value - 1) * 10, diskPage.value * 10).map((row) => ({
    ...row,
    size: formatBytes(row.total),
    usageText: `${formatBytes(row.used)} / ${row.percent.toFixed(1)}%`,
  })),
)

const netColumns = computed(() => [
  { key: 'name', label: t('vps.monitor.interface'), mono: true },
  { key: 'rxText', label: t('vps.monitor.download'), align: 'end' as const, mono: true },
  { key: 'txText', label: t('vps.monitor.upload'), align: 'end' as const, mono: true },
])
const netPage = ref(1)
const netRows = computed(() =>
  (data.value?.network.interfaces ?? [])
    .slice((netPage.value - 1) * 10, netPage.value * 10)
    .map((row) => ({ ...row, rxText: formatRate(row.rx), txText: formatRate(row.tx) })),
)

const hostItems = computed(() => {
  const value = data.value
  if (!value) return []
  const items = [
    { key: 'model', label: t('vps.monitor.cpuModel'), value: value.cpu.model || '-' },
    { key: 'cores', label: t('vps.monitor.cores'), value: String(value.cpu.cores) },
    { key: 'memory', label: t('vps.monitor.memoryTotal'), value: `${formatBytes(value.memory.used)} / ${formatBytes(value.memory.total)}` },
    { key: 'swap', label: t('vps.monitor.swap'), value: value.memory.swapTotal ? `${formatBytes(value.memory.swapUsed)} / ${formatBytes(value.memory.swapTotal)}` : '-' },
    { key: 'load', label: t('vps.monitor.loadAll'), value: value.load.map((item) => item.toFixed(2)).join(' / ') },
    { key: 'uptime', label: t('vps.monitor.uptime'), value: formatDuration(value.uptime, t) },
    { key: 'net', label: t('vps.monitor.netNow'), value: `↓ ${formatRate(value.network.rx)}  ↑ ${formatRate(value.network.tx)}` },
  ]
  for (const [index, sensor] of value.temperatures.slice(0, 6).entries()) {
    items.push({ key: `temp${index}`, label: sensor.name || t('vps.monitor.temperature'), value: `${sensor.celsius.toFixed(1)} °C` })
  }
  for (const [index, gpu] of value.gpus.entries()) items.push({ key: `gpu${index}`, label: `GPU ${index}`, value: gpu.name })
  return items
})
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('vps.monitor.title')" :description="t('vps.monitor.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <template v-else>
      <StatCard
        v-for="card in cards"
        :key="card.key"
        :label="card.label"
        :value="card.value"
        :delta="card.delta"
        :delta-label="card.deltaLabel"
        :trend="card.trend && card.trend.length > 1 ? card.trend : undefined"
        good="down"
      />

      <PageSection v-if="live.length > 1" :cols="4" :title="t('vps.monitor.liveUsage')" :description="t('vps.monitor.liveNote')">
        <TrendChart :label="t('vps.monitor.liveUsage')" :labels="liveLabels" :series="usage(live)" :format="percentText" />
      </PageSection>

      <PageSection v-if="live.length > 1" :cols="4" :title="t('vps.monitor.liveTraffic')" :description="t('vps.monitor.liveNote')">
        <TrendChart :label="t('vps.monitor.liveTraffic')" :labels="liveLabels" :series="traffic(live)" :format="formatRate" />
      </PageSection>

      <PageSection v-if="liveGpu.length > 1" :cols="4" :title="t('vps.monitor.liveGpu')" :description="t('vps.monitor.liveNote')">
        <TrendChart :label="t('vps.monitor.liveGpu')" :labels="liveGpuLabels" :series="gpuSeries(liveGpu)" :format="percentText" />
      </PageSection>

      <PageSection v-if="day.length > 1" :cols="4" :title="t('vps.monitor.usageChart')" :description="t('vps.monitor.chartNote')">
        <TrendChart :label="t('vps.monitor.usageChart')" :labels="dayLabels" :series="usage(day)" :format="percentText" />
      </PageSection>

      <PageSection v-if="day.length > 1" :cols="4" :title="t('vps.monitor.trafficChart')" :description="t('vps.monitor.chartNote')">
        <TrendChart :label="t('vps.monitor.trafficChart')" :labels="dayLabels" :series="traffic(day)" :format="formatRate" />
      </PageSection>

      <PageSection v-if="recentGpu.length > 1" :cols="4" :title="t('vps.monitor.gpuChart')" :description="t('vps.monitor.chartNote')">
        <TrendChart :label="t('vps.monitor.gpuChart')" :labels="recentGpuLabels" :series="gpuSeries(recentGpu)" :format="percentText" />
      </PageSection>

      <PageSection :cols="4" :title="t('vps.monitor.disks')">
        <DataTable :columns="diskColumns" :rows="diskRows" row-key="mount" :caption="t('vps.monitor.disks')" :empty="t('vps.monitor.noDisks')">
          <template #cell-usage="{ row }">
            <ProgressBar variant="inline" :label="String(row.mount)" :value="Number(row.percent)" :text="String(row.usageText)" />
          </template>
        </DataTable>
        <PaginationBar v-if="data.disks.length > 10" v-model="diskPage" :total="data.disks.length" />
      </PageSection>

      <PageSection :cols="4" :title="t('vps.monitor.host')">
        <DescriptionList :items="hostItems" />
      </PageSection>

      <PageSection :cols="4" :title="t('vps.monitor.network')">
        <DataTable :columns="netColumns" :rows="netRows" row-key="name" :caption="t('vps.monitor.network')" :empty="t('vps.monitor.noInterfaces')" />
        <PaginationBar v-if="data.network.interfaces.length > 10" v-model="netPage" :total="data.network.interfaces.length" />
      </PageSection>

      <MonitorAlertsCards />
    </template>
  </CardGrid>
</template>
