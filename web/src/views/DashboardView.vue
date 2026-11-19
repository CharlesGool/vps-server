<script setup lang="ts">
import {
  Activity,
  Archive,
  ArrowUpDown,
  Blocks,
  Cable,
  AppWindow,
  Earth,
  Gauge,
  Globe,
  HardDriveDownload,
  Network,
  Radio,
  Route,
  ScrollText,
  ShieldCheck,
  SlidersHorizontal,
  Terminal,
  Timer,
  UsersRound,
  Waypoints,
  Cpu,
  FolderOpen,
  Server,
  ServerCog,
} from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { SHOWCASE } from '@/app.config'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LinkCard from '@/components/app/LinkCard.vue'
import ModuleCard from '@/components/app/ModuleCard.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import RadioField from '@/components/app/RadioField.vue'
import StatCard from '@/components/app/StatCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ScheduleFields, { type Spec } from '@/components/vps/ScheduleFields.vue'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { formatBytes } from '@/lib/format'
import type { ResourceSummary } from '@/lib/monitor'
import { showToast } from '@/lib/toast'

// 主页: 主机总流量, 模块任务进度, 每个功能一张入口卡片(可启停的功能卡片右上角是开关).
interface ModuleItem {
  key: string
  href: string
  switchable: boolean
  enabled: boolean
  available: boolean
  occupiedPort?: number | null
  needsIpcert?: boolean
}
interface Total {
  used: number
  measured: number
  cap: number | null
  resetDay: number
  resetSpec: Spec | null
  timezone: string
  level: 'none' | 'ok' | 'warn' | 'over'
  since: string
  nextReset: string | null
  offset: number
  calibratedAt: string | null
  sources: { id: string; name: string; value: number; multiplier: number }[]
}
interface Dashboard {
  modules: ModuleItem[]
  busy: boolean
  job: { module: string; action: string; state: string; text: string } | null
  total: Total | null
  resources?: ResourceSummary
}

const { t } = useI18n()
const data = ref<Dashboard>()
const busy = ref(false)

const TITLES: Record<string, string> = {
  web_public: 'console.module_web_public',
  speedtest: 'console.speedtest',
  iperf3: 'console.iperf',
  proxy_nodes: 'console.proxy',
  caddy: 'console.domains',
  ipcert: 'console.ipcert',
  portfwd: 'console.portfwd',
  files: 'console.files',
  visitors: 'console.visitors',
  terminal: 'console.terminal_title',
  changelog: 'page.changelog',
  backup: 'console.backup',
  tasks: 'console.tasks',
  logs: 'console.module_detailed_logs',
  monitor: 'vps.monitor.title',
  system: 'vps.system.title',
  filemanager: 'vps.fm.title',
  fleet: 'vps.fleet.title',
}
const NAMES: Record<string, string> = { frps: 'FRPS', frpc: 'FRPC', tailscale: 'Tailscale' }
const ICONS: Record<string, typeof Gauge> = {
  web_public: Globe,
  speedtest: Gauge,
  iperf3: ArrowUpDown,
  proxy_nodes: Network,
  frps: Radio,
  frpc: Cable,
  tailscale: Waypoints,
  caddy: Earth,
  ipcert: ShieldCheck,
  portfwd: Route,
  files: HardDriveDownload,
  visitors: UsersRound,
  terminal: Terminal,
  changelog: ScrollText,
  backup: Archive,
  tasks: Timer,
  logs: Activity,
  monitor: Cpu,
  system: Server,
  filemanager: FolderOpen,
  fleet: ServerCog,
}
const title = (key: string) => NAMES[key] ?? t(TITLES[key] ?? key)

// 资源概览: 主页顶部一行 4 张数据卡, 详情在资源监控页
const resourceCards = computed(() => {
  const value = data.value?.resources
  if (!value) return []
  const memory = value.memory.total ? Math.round((value.memory.used * 1000) / value.memory.total) / 10 : 0
  const trend = (column: 1 | 2) => value.trend.map((row) => row[column]).filter((item): item is number => item != null)
  const ago = value.hourAgo
  return [
    { key: 'cpu', label: t('vps.monitor.cpu'), value: `${value.cpu.percent.toFixed(1)}%`, delta: ago ? Math.round((value.cpu.percent - ago.cpu) * 10) / 10 : 0, deltaLabel: t('vps.monitor.vsHourAgo'), trend: trend(1) },
    { key: 'memory', label: t('vps.monitor.memory'), value: `${memory.toFixed(1)}%`, delta: ago ? Math.round((memory - ago.memory) * 10) / 10 : 0, deltaLabel: t('vps.monitor.vsHourAgo'), trend: trend(2) },
    { key: 'disk', label: t('vps.monitor.disk'), value: value.disk ? `${value.disk.percent.toFixed(1)}%` : '-', delta: 0, deltaLabel: value.disk ? t('vps.monitor.diskFree', { free: formatBytes(value.disk.free) }) : '-', trend: [] },
    { key: 'load', label: t('vps.monitor.load'), value: value.load[0].toFixed(2), delta: value.load[2] ? Math.round(((value.load[0] - value.load[2]) / value.load[2]) * 100) : 0, deltaLabel: t('vps.monitor.vsLoad15'), trend: [] },
  ]
})

function detail(item: ModuleItem) {
  if (item.occupiedPort != null) return t('console.module_port_occupied', { port: item.occupiedPort })
  if (item.needsIpcert) return t('console.module_public_needs_ipcert')
  if (item.switchable && !item.available) return t('vps.dashboard.notInstalled')
  return undefined
}

// 有模块任务在运行时每 2 秒刷新一次; 控制台重启期间请求失败时继续等待
let timer: ReturnType<typeof setTimeout> | undefined
async function load() {
  clearTimeout(timer)
  try {
    data.value = await api<Dashboard>('dashboard')
  } catch (err) {
    if (isSignedOut(err)) return
    // 其他失败(多半是控制台正在重启): 继续等待, 下面会再试
  }
  if (!data.value || data.value.busy) timer = setTimeout(load, 2000)
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

const ERRORS: Record<string, string> = {
  module_busy: 'vps.dashboard.busy',
  module_job_failed: 'console.module_job_failed',
  module_source_missing: 'console.module_source_missing',
  module_tailscale_asset_missing: 'console.module_tailscale_asset_missing',
}
async function toggle(item: ModuleItem, enabled: boolean) {
  if (busy.value) return
  busy.value = true
  try {
    data.value = await api<Dashboard>('modules/action', { method: 'POST', body: { module: item.key, action: enabled ? 'enable' : 'disable' } })
    if (data.value.busy) timer = setTimeout(load, 2000)
  } catch (err) {
    const code = err instanceof ApiError ? err.code : ''
    showToast(t(ERRORS[code] ?? 'vps.common.failed'), 'destructive')
  } finally {
    busy.value = false
  }
}

// ---- 总流量 ----
const total = computed(() => data.value?.total)
const percent = computed(() => (total.value?.cap ? Math.min(100, (total.value.used * 100) / total.value.cap) : 0))
const figure = computed(() => {
  const value = total.value
  if (!value) return ''
  return value.cap != null
    ? t('vps.dashboard.usedOf', { used: formatBytes(value.used), cap: formatBytes(value.cap), percent: percent.value.toFixed(1) })
    : `${formatBytes(value.used)} · ${t('console.total_no_cap')}`
})
const meta = computed(() => {
  const value = total.value
  if (!value) return ''
  const reset = !value.nextReset
    ? t('console.total_no_reset')
    : value.resetSpec
      ? t('vps.dashboard.nextResetLocal', { date: value.nextReset, zone: value.timezone })
      : t('console.total_next_reset', { date: value.nextReset })
  return `${t('console.total_since', { date: value.since })} · ${reset}`
})
const sourceRows = computed(() => {
  const value = total.value
  if (!value) return []
  const basis = value.cap ?? value.used
  const rows = value.sources.map((source) => ({
    id: source.id,
    name: source.name,
    usage: source.multiplier !== 1 ? `${formatBytes(source.value / source.multiplier)} × ${source.multiplier} = ${formatBytes(source.value)}` : formatBytes(source.value),
    share: `${basis ? ((source.value * 100) / basis).toFixed(1) : '0.0'}%`,
    percent: basis ? Math.min(100, Math.max(0, (source.value * 100) / basis)) : 0,
  }))
  if (value.offset) {
    rows.push({
      id: 'calibration',
      name: t('console.total_calibration_row', { date: value.calibratedAt ?? '' }),
      usage: `${value.offset > 0 ? '+' : '−'}${formatBytes(Math.abs(value.offset))}`,
      share: `${basis ? ((Math.abs(value.offset) * 100) / basis).toFixed(1) : '0.0'}%`,
      percent: basis ? Math.min(100, (Math.abs(value.offset) * 100) / basis) : 0,
    })
  }
  return rows
})
const sourceColumns = computed(() => [
  { key: 'name', label: t('vps.dashboard.source') },
  { key: 'usage', label: t('vps.dashboard.usage'), align: 'end' as const, mono: true },
  { key: 'share', label: t('vps.dashboard.share'), align: 'end' as const, mono: true },
])

// 总流量设置和校准: 对话框里的短表单
const settingsOpen = ref(false)
const capGib = ref('')
// 重置: 不重置, 或和定时任务同一套的每周/每月/每年计划(服务器本地时间). 旧版本的"每月几号(UTC)"打开时换算成每月计划.
const resetOn = ref<'none' | 'schedule'>('schedule')
const resetSpec = ref<Spec>({ mode: 'monthly', day: 1, time: '00:00:00' })
const resetKey = ref(0)
const RESET_MODES: ('weekly' | 'monthly' | 'yearly')[] = ['weekly', 'monthly', 'yearly']
const resetChoices = computed(() => [
  { value: 'none' as const, label: t('console.node_reset_none') },
  { value: 'schedule' as const, label: t('console.node_reset_repeat') },
])
const calibrateOpen = ref(false)
const actualGib = ref('')
const dialogError = ref('')
function openSettings() {
  capGib.value = total.value?.cap != null ? String(total.value.cap / 1073741824) : ''
  const value = total.value
  resetOn.value = value?.resetSpec || value?.resetDay ? 'schedule' : 'none'
  resetSpec.value = value?.resetSpec ?? { mode: 'monthly', day: value?.resetDay || 1, time: '00:00:00' }
  resetKey.value += 1
  dialogError.value = ''
  settingsOpen.value = true
}
function openCalibrate() {
  actualGib.value = total.value?.offset ? String(total.value.used / 1073741824) : ''
  dialogError.value = ''
  calibrateOpen.value = true
}
async function saveTotal(path: string, body: unknown, close: () => void) {
  busy.value = true
  dialogError.value = ''
  try {
    data.value = await api<Dashboard>(path, { method: path === 'traffic/total' ? 'PUT' : 'POST', body })
    close()
    showToast(t('vps.dashboard.saved'), 'success')
  } catch {
    dialogError.value = t('vps.dashboard.invalid')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.dashboard')" root />

    <StatCard
      v-for="card in resourceCards"
      :key="card.key"
      :label="card.label"
      :value="card.value"
      :delta="card.delta"
      :delta-label="card.deltaLabel"
      :trend="card.trend.length > 1 ? card.trend : undefined"
      good="down"
    />

    <PageSection v-if="total" :cols="4" :title="t('console.total_title')" :description="meta">
      <p class="text-2xl font-semibold tabular-nums">{{ figure }}</p>
      <ProgressBar v-if="total.cap != null" :label="t('vps.dashboard.usedLabel')" :value="Math.round(percent)" />
      <AlertBanner v-if="total.level === 'warn' || total.level === 'over'" :tone="total.level === 'over' ? 'destructive' : 'warning'">
        {{ t(total.level === 'over' ? 'console.total_over' : 'console.total_warn') }}
      </AlertBanner>
      <DataTable
        v-if="sourceRows.length"
        :columns="sourceColumns"
        :rows="sourceRows.slice(0, 10)"
        row-key="id"
        :caption="t('console.total_by_source')"
        :empty="t('vps.dashboard.noTraffic')"
      >
        <template #cell-share="{ row }">
          <ProgressBar variant="inline" :label="String(row.name)" :value="Number(row.percent)" :text="String(row.share)" />
        </template>
      </DataTable>
      <p v-if="sourceRows.length" class="text-sm text-muted-foreground">{{ t('console.total_multiplier_note') }}</p>
      <FormActions>
        <Button variant="outline" :disabled="busy" @click="openCalibrate">{{ t('console.total_calibrate') }}</Button>
        <Button variant="outline" :disabled="busy" @click="openSettings"><SlidersHorizontal aria-hidden="true" />{{ t('console.total_settings') }}</Button>
      </FormActions>
    </PageSection>

    <PageSection v-if="data?.job" :cols="4" :title="t('vps.dashboard.job')">
      <AlertBanner :tone="data.job.state === 'failed' ? 'destructive' : data.job.state === 'done' ? 'success' : 'info'" role="status">{{ data.job.text }}</AlertBanner>
    </PageSection>

    <ModuleCard
      v-for="item in data?.modules ?? []"
      :key="item.key"
      :model-value="item.enabled"
      :to="item.href"
      :external="item.key === 'web_public' && item.enabled"
      :title="title(item.key)"
      :icon="ICONS[item.key] ?? Blocks"
      :detail="detail(item)"
      :switchable="item.switchable"
      :switch-disabled="busy || !!data?.busy || !item.available"
      :switch-label="t(item.enabled ? 'vps.dashboard.disable' : 'vps.dashboard.enable', { name: title(item.key) })"
      @update:model-value="toggle(item, $event)"
    />
    <!-- 组件样例入口只在开发和测试构建中提供 -->
    <LinkCard v-if="SHOWCASE" to="/showcase" :title="t('page.showcase')" :description="t('settings.showcaseDescription')" :icon="Blocks" />
    <LinkCard v-if="SHOWCASE" to="/scenes" :title="t('page.showcaseScenes')" :description="t('showcase.desc.scenes')" :icon="AppWindow" />

    <AppDialog v-model:open="settingsOpen" :title="t('console.total_settings')" :description="t('console.total_hint')">
      <FormField v-slot="field" :label="t('console.total_cap_gib')" :span="6">
        <Input :id="field.id" v-model="capGib" inputmode="decimal" :placeholder="t('console.node_unlimited')" />
      </FormField>
      <FormField :label="t('console.node_reset_schedule')" group :span="6" :error="dialogError">
        <RadioField v-model="resetOn" :options="resetChoices" :label="t('console.node_reset_schedule')" />
      </FormField>
      <ScheduleFields v-if="resetOn === 'schedule'" :key="resetKey" v-model="resetSpec" :timezone="total?.timezone ?? ''" :modes="RESET_MODES" :once="false" />
      <template #footer>
        <Button variant="outline" @click="settingsOpen = false">{{ t('console.node_cancel') }}</Button>
        <Button :disabled="busy" @click="saveTotal('traffic/total', { capGib: capGib.trim() || null, resetDay: 0, resetSpec: resetOn === 'schedule' ? resetSpec : null }, () => (settingsOpen = false))">
          {{ t('console.total_save') }}
        </Button>
      </template>
    </AppDialog>
    <AppDialog v-model:open="calibrateOpen" :title="t('console.total_calibrate_title')" :description="t('console.total_calibrate_hint')">
      <FormField v-slot="field" :label="t('console.total_actual_gib')" :error="dialogError">
        <Input :id="field.id" v-model="actualGib" inputmode="decimal" />
      </FormField>
      <p class="text-sm text-muted-foreground">{{ t('console.total_calibrate_measured', { value: formatBytes(total?.measured ?? 0) }) }}</p>
      <template #footer>
        <Button variant="outline" @click="calibrateOpen = false">{{ t('console.node_cancel') }}</Button>
        <Button :disabled="busy" @click="saveTotal('traffic/total/calibrate', { actualGib: actualGib.trim() || null }, () => (calibrateOpen = false))">
          {{ t('console.total_calibrate_save') }}
        </Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
