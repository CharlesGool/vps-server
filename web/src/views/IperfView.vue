<script setup lang="ts">
import { Pencil, Play, Power, Timer } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import ModuleInstall from '@/components/vps/ModuleInstall.vue'
import PrivateValue from '@/components/vps/PrivateValue.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// iperf3: 服务端窗口(状态和倒计时, 端口和命令默认遮住, 开启/延长/关闭, 修改端口的对话框)和向外测试的客户端并排, 下面是流量卡片.
// 模块还没安装时只显示安装卡片.
interface Iperf {
  installed: boolean
  enabled: boolean
  open: boolean
  remaining: number
  defaultMinutes: number
  maxMinutes: number
  message: string | null
}
interface ClientResult {
  status: 'done' | 'invalid' | 'missing' | 'busy' | 'timeout' | 'failed' | 'disabled'
  detail?: string
  mbps?: number
  jitter_ms?: number
  loss_percent?: number
  retransmits?: number
}

const { t } = useI18n()
const data = ref<Iperf>()
const minutes = ref(10)
const remaining = ref(0)
const busy = ref(false)

let tick: ReturnType<typeof setInterval> | undefined
function apply(value: Iperf) {
  data.value = value
  remaining.value = value.remaining
  clearInterval(tick)
  // 窗口开着时每秒倒数; 到 0 时服务器已经自己关闭, 重新读取状态
  if (value.open) {
    tick = setInterval(() => {
      remaining.value = Math.max(0, remaining.value - 1)
      if (remaining.value === 0) {
        clearInterval(tick)
        void load()
      }
    }, 1000)
  }
  if (value.message) {
    const good = ['iperf_opened', 'iperf_extended', 'iperf_shut', 'iperf_port_saved'].includes(value.message)
    showToast(t(`console.${value.message}`, { port: '••••••' }), good ? 'success' : 'destructive')
  }
}
async function load() {
  try {
    const value = await api<Iperf>('iperf')
    if (!data.value) minutes.value = value.defaultMinutes
    apply(value)
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)
onBeforeUnmount(() => clearInterval(tick))

async function send(path: string, method: string, body: unknown) {
  busy.value = true
  try {
    apply(await api<Iperf>(path, { method, body }))
    return true
  } catch (err) {
    if (err instanceof ApiError && err.code === 'iperf_port_invalid') showToast(t('console.iperf_port_invalid'), 'destructive')
    else if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

const state = computed(() =>
  data.value?.open
    ? t('console.iperf_state_open', { port: '••••••', mins: Math.floor(remaining.value / 60), secs: remaining.value % 60 })
    : t('console.iperf_state_closed', { port: '••••••' }),
)
const facts = computed(() => [
  { key: 'state', label: t('console.iperf_status') },
  { key: 'port', label: t('console.iperf_port') },
  { key: 'cmd-speed', label: t('console.iperf_cmd_speed') },
  { key: 'cmd-single', label: t('console.iperf_cmd_single') },
  { key: 'cmd-multi', label: t('console.iperf_cmd_multi') },
])

// ---- 修改端口 ----
// 当前端口遮住, 输入框留空, 占位符同样遮住
const portOpen = ref(false)
const newPort = ref('')
async function savePort() {
  const port = Number(newPort.value)
  if (!Number.isInteger(port)) return showToast(t('console.iperf_port_invalid'), 'destructive')
  if (await send('iperf/port', 'PUT', { port })) {
    newPort.value = ''
    portOpen.value = false
  }
}

// ---- 客户端 ----
const client = ref({ host: '', port: 5201, seconds: 10, mbps: 100, protocol: 'tcp' as 'tcp' | 'udp', direction: 'upload' as 'upload' | 'download' })
const testing = ref(false)
const result = ref<ClientResult>()
const protocols = [
  { value: 'tcp' as const, label: 'TCP' },
  { value: 'udp' as const, label: 'UDP' },
]
const directions = computed(() => [
  { value: 'upload' as const, label: t('console.iperf_client_upload') },
  { value: 'download' as const, label: t('console.iperf_client_download') },
])
async function runClient() {
  if (testing.value) return
  testing.value = true
  result.value = undefined
  try {
    result.value = await api<ClientResult>('iperf/client', { method: 'POST', body: client.value })
  } catch (err) {
    if (!isSignedOut(err)) result.value = { status: 'invalid' }
  } finally {
    testing.value = false
  }
}
const metrics = computed(() => {
  const value = result.value
  if (value?.status !== 'done') return ''
  const parts = [`${t('console.iperf_client_speed')}: ${value.mbps!.toFixed(2)} Mbit/s`]
  if (value.jitter_ms != null) parts.push(`${t('console.iperf_client_jitter')}: ${value.jitter_ms}ms`)
  if (value.loss_percent != null) parts.push(`${t('console.iperf_client_loss')}: ${value.loss_percent}%`)
  if (value.retransmits != null) parts.push(`${t('console.iperf_client_retransmits')}: ${value.retransmits}`)
  return parts.join(' · ')
})
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.iperf_heading')" :description="t('vps.iperf.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <ModuleInstall v-else-if="!data.installed" module="iperf3" name="iPerf 3" @installed="load" />

    <template v-else>
      <!-- 服务端: 状态, 遮住的端口和命令, 开启时长和开关 -->
      <CardForm @submit.prevent="send('iperf/open', 'POST', { minutes })">
        <PageSection :cols="2" :title="t('console.iperf_server_heading')" :description="t('console.iperf_info')">
          <AlertBanner v-if="!data.enabled" tone="warning">{{ t('console.iperf_disabled') }}</AlertBanner>
          <DescriptionList :items="facts">
            <template #value-state>
              <StatusBadge :tone="data.open ? 'success' : 'neutral'" aria-live="polite">{{ state }}</StatusBadge>
            </template>
            <template #value-port>
              <PrivateValue source="iperf" field="port" :label="t('console.iperf_port')" />
            </template>
            <template v-for="command in ['cmd-speed', 'cmd-single', 'cmd-multi']" :key="command" #[`value-${command}`]="{ item }">
              <PrivateValue source="iperf" :field="command" :label="item.label" />
            </template>
          </DescriptionList>
          <FormField v-slot="field" :label="t('console.iperf_minutes')">
            <NumberField :id="field.id" v-model="minutes" :min="1" :max="data.maxMinutes" />
          </FormField>
          <FormActions>
            <!-- 修改端口: 窗口开着时不能改 -->
            <Button type="button" variant="outline" :disabled="busy || data.open" @click="portOpen = true">
              <Pencil aria-hidden="true" />{{ t('console.iperf_change_port') }}
            </Button>
            <Button v-if="data.open" type="button" variant="outline" :disabled="busy" @click="send('iperf/close', 'POST', {})">
              <Power aria-hidden="true" />{{ t('console.iperf_close') }}
            </Button>
            <Button type="submit" :disabled="busy">
              <Timer aria-hidden="true" />{{ data.open ? t('console.iperf_extend') : t('console.iperf_open') }}
            </Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <!-- 客户端: 从本机向另一台 iperf3 服务器测试 -->
      <CardForm @submit.prevent="runClient">
        <PageSection :cols="2" :title="t('console.iperf_client_heading')">
          <AlertBanner v-if="result?.status === 'done'" tone="success" :title="t('console.iperf_client_done')">{{ metrics }}</AlertBanner>
          <AlertBanner v-else-if="result" tone="destructive">{{ t(`console.iperf_client_${result.status}`) }} {{ result.detail ?? '' }}</AlertBanner>
          <FormField v-slot="field" :label="t('console.iperf_client_host')" :span="6">
            <Input :id="field.id" v-model="client.host" inputmode="decimal" autocomplete="off" required />
          </FormField>
          <FormField v-slot="field" :label="t('console.iperf_client_port')" :span="6">
            <NumberField :id="field.id" v-model="client.port" :min="1" :max="65535" :grouping="false" />
          </FormField>
          <FormField v-slot="field" :label="t('console.iperf_client_seconds')" :span="6">
            <NumberField :id="field.id" v-model="client.seconds" :min="1" :max="30" />
          </FormField>
          <FormField v-slot="field" :label="t('console.iperf_client_mbps')" :span="6">
            <NumberField :id="field.id" v-model="client.mbps" :min="1" :max="1000" />
          </FormField>
          <FormField :label="t('console.iperf_client_protocol')" group :span="6">
            <SegmentedControl v-model="client.protocol" :options="protocols" :label="t('console.iperf_client_protocol')" />
          </FormField>
          <FormField :label="t('console.iperf_client_direction')" group :span="6">
            <SegmentedControl v-model="client.direction" :options="directions" :label="t('console.iperf_client_direction')" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="testing || !client.host.trim()">
              <Play aria-hidden="true" />{{ testing ? t('console.running') : t('console.iperf_client_start') }}
            </Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <TrafficCard feature="iperf3" />

      <AppDialog v-model:open="portOpen" :title="t('console.iperf_change_port')" :description="t('vps.iperf.portDescription')">
        <FormField v-slot="field" :label="t('console.iperf_port')">
          <Input :id="field.id" v-model="newPort" inputmode="numeric" autocomplete="off" placeholder="••••••" @keydown.enter.prevent="savePort" />
        </FormField>
        <template #footer>
          <Button variant="outline" @click="portOpen = false">{{ t('console.node_cancel') }}</Button>
          <Button :disabled="busy || !newPort.trim()" @click="savePort">{{ t('console.iperf_save_port') }}</Button>
        </template>
      </AppDialog>
    </template>
  </CardGrid>
</template>
