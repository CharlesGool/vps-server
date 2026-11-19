<script setup lang="ts">
import { ExternalLink, LogIn, LogOut, RefreshCw, RotateCw, Save, ScrollText } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import CheckboxField from '@/components/app/CheckboxField.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import SelectMenu from '@/components/app/SelectMenu.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import ModuleInstall from '@/components/vps/ModuleInstall.vue'
import PrivateValue from '@/components/vps/PrivateValue.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, isSignedOut } from '@/lib/api'
import { formatBytes } from '@/lib/format'
import { showToast } from '@/lib/toast'

// Tailscale: 状态(服务状态, Tailnet, 地址默认遮住, 重启, 连接或退出), 连通性检查, 设置(一个表单), 设备表格, 流量.
// 运行日志在"详细日志"页的 Tailscale 来源里.
const SETTINGS = ['accept-dns', 'accept-routes', 'advertise-exit-node', 'exit-node-allow-lan-access', 'shields-up', 'snat-subnet-routes', 'ssh', 'webclient'] as const
type SettingName = (typeof SETTINGS)[number]
const LABELS: Record<SettingName, string> = {
  'accept-dns': 'tailscale_accept_dns',
  'accept-routes': 'tailscale_accept_routes',
  'advertise-exit-node': 'tailscale_advertise_exit',
  'exit-node-allow-lan-access': 'tailscale_exit_lan',
  'shields-up': 'tailscale_shields',
  'snat-subnet-routes': 'tailscale_snat',
  ssh: 'tailscale_ssh',
  webclient: 'tailscale_webclient',
}
type Device = { id: string; name: string; online: boolean; os: string; relay: string; rx: number; tx: number; lastSeen: string; ipv4: boolean; ipv6: boolean }
interface Tailscale {
  installed: boolean
  available?: boolean
  state?: string
  version?: string
  tun?: boolean | null
  present?: { controlServer: boolean; ipv4: boolean; ipv6: boolean; account: boolean }
  authUrl?: string | null
  settings?: { bools: Record<SettingName, boolean | null>; routes: string; exit: string; relay: boolean; memory: boolean | null }
  subnets?: string[]
  exitNodes?: { value: string; label: string }[]
  devices?: Device[]
}
interface Netcheck {
  running: boolean
  failed?: boolean
  derp?: string
  endpoint?: boolean
  checks?: Record<'varies' | 'ipv4' | 'ipv6' | 'udp' | 'upnp' | 'pcp' | 'pmp' | 'hairpinning', boolean | null>
}

const { t } = useI18n()
const data = ref<Tailscale>()
const net = ref<Netcheck>()
const busy = ref(false)
const running = computed(() => data.value?.state === 'Running')

// 设置表单: 读到状态后填入
const bools = ref<Partial<Record<SettingName, boolean>>>({})
const memory = ref(false)
const routes = ref('')
const exitNode = ref('')
const relay = ref('')
function fill(value: Tailscale) {
  const settings = value.settings
  if (!settings) return
  bools.value = Object.fromEntries(SETTINGS.map((name) => [name, settings.bools[name] === true]))
  memory.value = settings.memory === true
  routes.value = settings.routes || '-'
  exitNode.value = settings.exit || '-'
  relay.value = ''
}
async function loadNetcheck() {
  try {
    net.value = await api<Netcheck>('tailscale/netcheck')
  } catch {
    net.value = { running: true, failed: true }
  }
}
async function load() {
  try {
    data.value = await api<Tailscale>('tailscale')
    fill(data.value)
    if (data.value.available) void loadNetcheck()
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)

async function send(path: string, body: unknown, method = 'POST') {
  busy.value = true
  try {
    data.value = await api<Tailscale>(path, { method, body })
    fill(data.value)
    showToast(t('vps.common.done'), 'success')
    return true
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('legacy.tailscale_action_failed'), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

// ---- 状态 ----
const facts = computed(() => {
  const value = data.value
  if (!value?.present) return []
  return [
    { key: 'state', label: t('legacy.tailscale_state'), value: value.state },
    { key: 'controlServer', label: t('legacy.tailscale_control_server') },
    { key: 'account', label: t('legacy.tailscale_account') },
    { key: 'ipv4', label: t('legacy.tailscale_ipv4') },
    { key: 'ipv6', label: t('legacy.tailscale_ipv6') },
    { key: 'version', label: t('legacy.tailscale_version'), value: value.version || '—' },
    { key: 'tun', label: t('legacy.tailscale_tun'), value: value.tun == null ? '—' : t(value.tun ? 'legacy.tailscale_yes' : 'legacy.tailscale_no') },
  ]
})
const PRIVATE = { controlServer: 'tailscale_control_server', account: 'tailscale_account', ipv4: 'tailscale_ipv4', ipv6: 'tailscale_ipv6' } as const
// 写在模板属性里的网址会让 vue-tsc 误判后面的插槽变量, 所以放在这里
const SERVER_EXAMPLE = 'https://controlplane.tailscale.com'
const loginServer = ref('')
const authKey = ref('')
async function connect() {
  if (await send('tailscale/connect', { loginServer: loginServer.value.trim(), authKey: authKey.value.trim() })) authKey.value = ''
}
// Tailscale Web 管理界面在本机的 Tailscale IPv4 的 5252 端口; 只接受 100.64.0.0/10 的地址
async function openWeb() {
  try {
    const { value } = await api<{ value: string }>('private-value?id=tailscale-tailscale_ipv4&field=address')
    const parts = /^\d+\.\d+\.\d+\.\d+$/.test(value) ? value.split('.').map(Number) : []
    if (parts.length !== 4 || parts[0] !== 100 || parts[1]! < 64 || parts[1]! > 127 || parts.slice(2).some((part) => part > 255)) throw new Error('address')
    window.location.assign(`http://${value}:5252/`)
  } catch {
    showToast(t('legacy.tailscale_web_open_failed'), 'destructive')
  }
}

// ---- 连通性 ----
const checkNames = computed(() => ({
  varies: t('legacy.tailscale_varies'),
  ipv4: 'IPv4',
  ipv6: 'IPv6',
  udp: 'UDP',
  upnp: 'UPnP',
  pcp: 'PCP',
  pmp: 'NAT-PMP',
  hairpinning: t('legacy.tailscale_hairpinning'),
}))
const yesNo = (value: boolean | null | undefined) => (value == null ? '—' : t(value ? 'legacy.tailscale_yes' : 'legacy.tailscale_no'))

// ---- 设置 ----
const routeOptions = computed(() => [{ value: '-', label: t('vps.tailscale.none') }, ...(data.value?.subnets ?? []).map((value) => ({ value, label: value }))])
const exitOptions = computed(() => [{ value: '-', label: t('vps.tailscale.none') }, ...(data.value?.exitNodes ?? [])])
async function saveSettings() {
  const settings = data.value!.settings!
  const changeable = Object.fromEntries(
    SETTINGS.filter((name) => settings.bools[name] !== null && (name !== 'webclient' || running.value)).map((name) => [name, bools.value[name] === true]),
  )
  const relayValue = relay.value.trim() || null
  await send(
    'tailscale/settings',
    {
      bools: changeable,
      memory: settings.memory === null ? null : memory.value,
      routes: routes.value === '-' ? '' : routes.value,
      exit: exitNode.value === '-' ? '' : exitNode.value,
      relay: relayValue,
    },
    'PUT',
  )
}

// 只清除节点中继端口, 其他设置不变
async function clearRelayPort() {
  await send('tailscale/settings', { relay: '' }, 'PUT')
}

// ---- 设备 ----
const page = ref(1)
const devices = computed(() => data.value?.devices ?? [])
const deviceRows = computed(() => devices.value.slice((page.value - 1) * 10, page.value * 10))
const deviceColumns = computed(() => [
  { key: 'name', label: t('legacy.tailscale_device') },
  { key: 'online', label: t('legacy.tailscale_state') },
  { key: 'address', label: t('legacy.tailscale_address') },
  { key: 'os', label: t('legacy.tailscale_os') },
  { key: 'relay', label: t('legacy.tailscale_relay') },
  { key: 'traffic', label: t('legacy.tailscale_rx_tx'), align: 'end' as const, mono: true },
  { key: 'lastSeen', label: t('legacy.tailscale_last_seen'), mono: true },
])
</script>

<template>
  <CardGrid>
    <PageHeader title="Tailscale" :description="t('vps.tailscale.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <ModuleInstall v-else-if="!data.installed" module="tailscale" name="Tailscale" @installed="load" />

    <PageSection v-else-if="!data.available" :cols="4" title="Tailscale">
      <AlertBanner tone="destructive">{{ t('legacy.tailscale_unavailable') }}</AlertBanner>
      <FormActions>
        <Button as-child variant="outline">
          <RouterLink :to="{ path: '/settings/logs', query: { source: 'tailscale' } }"><ScrollText aria-hidden="true" />{{ t('vps.tailscale.logs') }}</RouterLink>
        </Button>
        <Button variant="outline" :disabled="busy" @click="send('tailscale/restart', {})"><RotateCw aria-hidden="true" />{{ t('legacy.tailscale_restart') }}</Button>
      </FormActions>
    </PageSection>

    <template v-else>
      <!-- 状态: 未连接时下面是连接表单 -->
      <CardForm @submit.prevent="connect">
        <PageSection :cols="4" :title="t('vps.tailscale.status')">
          <DescriptionList :items="facts">
            <template #value-state>
              <StatusBadge :tone="running ? 'success' : 'warning'">{{ data.state }}</StatusBadge>
            </template>
            <template v-for="key in (['controlServer', 'account', 'ipv4', 'ipv6'] as const)" :key="key" #[`value-${key}`]>
              <PrivateValue v-if="data.present?.[key]" :source="`tailscale-${PRIVATE[key]}`" field="address" :label="t(`legacy.${PRIVATE[key]}`)" />
              <template v-else>—</template>
            </template>
          </DescriptionList>
          <AlertBanner v-if="data.authUrl" tone="warning">
            <a :href="data.authUrl" target="_blank" rel="noopener noreferrer" class="font-medium underline">{{ t('legacy.tailscale_authorize') }}</a>
          </AlertBanner>
          <template v-if="!running">
            <FormField v-slot="field" :label="t('legacy.tailscale_login_server')">
              <Input :id="field.id" v-model="loginServer" type="url" maxlength="255" :placeholder="SERVER_EXAMPLE" autocomplete="off" />
            </FormField>
            <FormField v-slot="field" :label="t('legacy.tailscale_auth_key')">
              <PasswordInput :id="field.id" v-model="authKey" autocomplete="off" maxlength="2048" />
            </FormField>
          </template>
          <FormActions>
            <Button as-child variant="outline">
              <RouterLink :to="{ path: '/settings/logs', query: { source: 'tailscale' } }"><ScrollText aria-hidden="true" />{{ t('vps.tailscale.logs') }}</RouterLink>
            </Button>
            <Button type="button" variant="outline" :disabled="busy" @click="send('tailscale/restart', {})"><RotateCw aria-hidden="true" />{{ t('legacy.tailscale_restart') }}</Button>
            <Button v-if="running && data.settings?.bools.webclient" type="button" variant="outline" @click="openWeb"><ExternalLink aria-hidden="true" />{{ t('legacy.tailscale_open_web') }}</Button>
            <ConfirmDialog
              v-if="running"
              :title="t('legacy.tailscale_logout')"
              :description="t('legacy.tailscale_logout_confirm')"
              :confirm-label="t('legacy.tailscale_logout')"
              danger
              @confirm="send('tailscale/logout', { confirm: true })"
            >
              <template #trigger>
                <Button type="button" variant="destructive" :disabled="busy"><LogOut aria-hidden="true" />{{ t('legacy.tailscale_logout') }}</Button>
              </template>
            </ConfirmDialog>
            <Button v-else type="submit" :disabled="busy"><LogIn aria-hidden="true" />{{ t('legacy.tailscale_connect') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <!-- 连通性: 检查较慢, 单独读取 -->
      <PageSection :cols="4" :title="t('legacy.tailscale_connectivity')">
        <LoadingState v-if="!net" />
        <AlertBanner v-else-if="!net.running" tone="info">{{ t('vps.tailscale.notRunning') }}</AlertBanner>
        <AlertBanner v-else-if="net.failed" tone="warning">{{ t('legacy.tailscale_unavailable') }}</AlertBanner>
        <template v-else>
          <DescriptionList
            :items="[
              { key: 'derp', label: t('legacy.tailscale_derp'), value: net.derp || '—' },
              { key: 'endpoint', label: t('legacy.tailscale_public_endpoint') },
            ]"
          >
            <template #value-endpoint>
              <PrivateValue v-if="net.endpoint" source="tailscale-tailscale_public_endpoint" field="address" :label="t('legacy.tailscale_public_endpoint')" />
              <template v-else>—</template>
            </template>
          </DescriptionList>
          <InlineGroup>
            <StatusBadge v-for="(value, key) in net.checks" :key="key" :tone="value === true ? 'success' : 'neutral'">{{ checkNames[key] }}: {{ yesNo(value) }}</StatusBadge>
          </InlineGroup>
        </template>
      </PageSection>

      <!-- 设置: 一个表单, 一起保存 -->
      <CardForm v-if="data.settings" @submit.prevent="saveSettings">
        <PageSection :cols="4" :title="t('legacy.tailscale_tab_settings')">
          <CheckboxField
            v-for="name in SETTINGS"
            :key="name"
            v-model="bools[name]"
            :label="t(`legacy.${LABELS[name]}`)"
            :disabled="data.settings.bools[name] === null || (name === 'webclient' && !running)"
            :span="4"
          />
          <CheckboxField v-model="memory" :label="t('legacy.tailscale_memory')" :disabled="data.settings.memory === null" :span="4" />
          <FormField v-slot="field" :label="t('legacy.tailscale_routes')" :span="4">
            <SelectMenu :id="field.id" v-model="routes" :options="routeOptions" :label="t('legacy.tailscale_routes')" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.tailscale_exit_node')" :span="4">
            <SelectMenu :id="field.id" v-model="exitNode" :options="exitOptions" :label="t('legacy.tailscale_exit_node')" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.tailscale_peer_relay')" :span="4" :help="data.settings.relay ? t('vps.tailscale.relaySet') : undefined">
            <Input :id="field.id" v-model="relay" inputmode="numeric" maxlength="5" placeholder="••••••" autocomplete="off" />
          </FormField>
          <FormActions>
            <Button v-if="data.settings.relay" type="button" variant="outline" :disabled="busy" @click="clearRelayPort">{{ t('legacy.tailscale_clear') }} {{ t('legacy.tailscale_peer_relay') }}</Button>
            <Button type="submit" :disabled="busy"><Save aria-hidden="true" />{{ t('legacy.frp_save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <PageSection :cols="4" :title="`${t('legacy.tailscale_devices')} (${devices.length})`">
        <DataTable :columns="deviceColumns" :rows="deviceRows" row-key="id" :caption="t('legacy.tailscale_devices')" :empty="t('legacy.tailscale_no_devices')">
          <template #cell-online="{ row }">
            <StatusBadge :tone="row.online ? 'success' : 'neutral'">{{ t(row.online ? 'legacy.tailscale_online' : 'legacy.tailscale_offline') }}</StatusBadge>
          </template>
          <template #cell-address="{ row }">
            <PrivateValue v-if="row.ipv4" :source="`tailscale-peer-${row.id}`" field="ipv4" :label="`IPv4 ${row.name}`" />
            <PrivateValue v-if="row.ipv6" :source="`tailscale-peer-${row.id}`" field="ipv6" :label="`IPv6 ${row.name}`" />
          </template>
          <template #cell-relay="{ row }">{{ row.relay || '—' }}</template>
          <template #cell-traffic="{ row }">{{ formatBytes(row.rx) }} / {{ formatBytes(row.tx) }}</template>
          <template #cell-lastSeen="{ row }">{{ row.online ? t('legacy.tailscale_online') : row.lastSeen || '—' }}</template>
        </DataTable>
        <PaginationBar v-if="devices.length > 10" v-model="page" :total="devices.length" />
        <FormActions>
          <Button variant="outline" :disabled="busy" @click="load"><RefreshCw aria-hidden="true" />{{ t('legacy.tailscale_refresh') }}</Button>
        </FormActions>
      </PageSection>

      <TrafficCard feature="tailscale" />
    </template>
  </CardGrid>
</template>
