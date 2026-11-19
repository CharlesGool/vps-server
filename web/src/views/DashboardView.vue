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
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { formatBytes } from '@/lib/format'
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
}

const { t } = useI18n()
const data = ref<Dashboard>()
const busy = ref(false)

const TITLES: Record<string, string> = {
  web_public: 'legacy.module_web_public',
  speedtest: 'legacy.speedtest',
  iperf3: 'legacy.iperf',
  proxy_nodes: 'legacy.proxy',
  caddy: 'legacy.domains',
  ipcert: 'legacy.ipcert',
  portfwd: 'legacy.portfwd',
  files: 'legacy.files',
  visitors: 'legacy.visitors',
  terminal: 'legacy.terminal_title',
  changelog: 'page.changelog',
  backup: 'legacy.backup',
  tasks: 'legacy.tasks',
  logs: 'legacy.module_detailed_logs',
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
}
const title = (key: string) => NAMES[key] ?? t(TITLES[key] ?? key)

function detail(item: ModuleItem) {
  if (item.occupiedPort != null) return t('legacy.module_port_occupied', { port: item.occupiedPort })
  if (item.needsIpcert) return t('legacy.module_public_needs_ipcert')
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
  module_job_failed: 'legacy.module_job_failed',
  module_source_missing: 'legacy.module_source_missing',
  module_tailscale_asset_missing: 'legacy.module_tailscale_asset_missing',
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
    : `${formatBytes(value.used)} · ${t('legacy.total_no_cap')}`
})
const meta = computed(() => {
  const value = total.value
  if (!value) return ''
  const reset = value.nextReset ? t('legacy.total_next_reset', { date: value.nextReset }) : t('legacy.total_no_reset')
  return `${t('legacy.total_since', { date: value.since })} · ${reset}`
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
  }))
  if (value.offset) {
    rows.push({
      id: 'calibration',
      name: t('legacy.total_calibration_row', { date: value.calibratedAt ?? '' }),
      usage: `${value.offset > 0 ? '+' : '−'}${formatBytes(Math.abs(value.offset))}`,
      share: `${basis ? ((Math.abs(value.offset) * 100) / basis).toFixed(1) : '0.0'}%`,
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
const resetDay = ref(1)
const calibrateOpen = ref(false)
const actualGib = ref('')
const dialogError = ref('')
function openSettings() {
  capGib.value = total.value?.cap != null ? String(total.value.cap / 1073741824) : ''
  resetDay.value = total.value?.resetDay ?? 1
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

    <PageSection v-if="data?.job" :cols="4" :title="t('vps.dashboard.job')">
      <AlertBanner :tone="data.job.state === 'failed' ? 'destructive' : data.job.state === 'done' ? 'success' : 'info'" role="status">{{ data.job.text }}</AlertBanner>
    </PageSection>

    <PageSection v-if="total" :cols="4" :title="t('legacy.total_title')" :description="meta">
      <p class="text-2xl font-semibold tabular-nums">{{ figure }}</p>
      <ProgressBar v-if="total.cap != null" :label="t('vps.dashboard.usedLabel')" :value="Math.round(percent)" />
      <AlertBanner v-if="total.level === 'warn' || total.level === 'over'" :tone="total.level === 'over' ? 'destructive' : 'warning'">
        {{ t(total.level === 'over' ? 'legacy.total_over' : 'legacy.total_warn') }}
      </AlertBanner>
      <DataTable
        v-if="sourceRows.length"
        :columns="sourceColumns"
        :rows="sourceRows.slice(0, 10)"
        row-key="id"
        :caption="t('legacy.total_by_source')"
        :empty="t('vps.dashboard.noTraffic')"
      />
      <p v-if="sourceRows.length" class="text-sm text-muted-foreground">{{ t('legacy.total_multiplier_note') }}</p>
      <FormActions>
        <Button variant="outline" :disabled="busy" @click="openCalibrate">{{ t('legacy.total_calibrate') }}</Button>
        <Button variant="outline" :disabled="busy" @click="openSettings"><SlidersHorizontal aria-hidden="true" />{{ t('legacy.total_settings') }}</Button>
      </FormActions>
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

    <AppDialog v-model:open="settingsOpen" :title="t('legacy.total_settings')" :description="t('legacy.total_hint')">
      <FormField v-slot="field" :label="t('legacy.total_cap_gib')" :span="6">
        <Input :id="field.id" v-model="capGib" inputmode="decimal" :placeholder="t('legacy.node_unlimited')" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.total_reset_day')" :span="6" :error="dialogError">
        <NumberField :id="field.id" v-model="resetDay" :min="0" :max="28" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="settingsOpen = false">{{ t('legacy.node_cancel') }}</Button>
        <Button :disabled="busy" @click="saveTotal('traffic/total', { capGib: capGib.trim() || null, resetDay }, () => (settingsOpen = false))">
          {{ t('legacy.total_save') }}
        </Button>
      </template>
    </AppDialog>
    <AppDialog v-model:open="calibrateOpen" :title="t('legacy.total_calibrate_title')" :description="t('legacy.total_calibrate_hint')">
      <FormField v-slot="field" :label="t('legacy.total_actual_gib')" :error="dialogError">
        <Input :id="field.id" v-model="actualGib" inputmode="decimal" />
      </FormField>
      <p class="text-sm text-muted-foreground">{{ t('legacy.total_calibrate_measured', { value: formatBytes(total?.measured ?? 0) }) }}</p>
      <template #footer>
        <Button variant="outline" @click="calibrateOpen = false">{{ t('legacy.node_cancel') }}</Button>
        <Button :disabled="busy" @click="saveTotal('traffic/total/calibrate', { actualGib: actualGib.trim() || null }, () => (calibrateOpen = false))">
          {{ t('legacy.total_calibrate_save') }}
        </Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
