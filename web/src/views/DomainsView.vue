<script setup lang="ts">
import { Earth, History, KeyRound, Plus } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import CheckboxField from '@/components/app/CheckboxField.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import SelectMenu from '@/components/app/SelectMenu.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import ModuleInstall from '@/components/vps/ModuleInstall.vue'
import PrivateValue from '@/components/vps/PrivateValue.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// 域名转发: 概况(本机公网地址, DNS 检查, 变更记录, 添加域名), 流量, 每个主域名一张站点表格(行操作在菜单里), Cloudflare 令牌.
// 添加和编辑站点在对话框里; 站点的证书, DNS 和访问限制在"详情"对话框里.
type Tone = 'neutral' | 'success' | 'warning' | 'destructive' | 'info'
type Site = {
  host: string
  zone: string
  enabled: boolean
  console: boolean
  hasPort: boolean
  scheme: string
  backendTls: boolean
  upstreamHost: boolean
  options: string
  aliases: string[]
  allowIps: string[]
  authUser: string
  addedAt: string
  badges: { tone: Tone; text: string }[]
  certText: string
  dnsText: string
  aliasesText: string
  accessText: string
}
type Token = { id: string; name: string; state: 'ok' | 'auth' | 'unreachable'; checked: string; zones: { zone: string; sites: number }[] }
interface Domains {
  installed: boolean
  running?: boolean
  dns?: { ipv4: boolean; ipv6: boolean; checked: string; error: string | null }
  history?: { time: string; text: string }[]
  zones?: string[]
  consoleTarget?: boolean
  groups?: { zone: string; sites: Site[] }[]
  tokens?: Token[]
  message?: string | null
  warning?: string | null
}

const { t } = useI18n()
const router = useRouter()
const data = ref<Domains>()
const busy = ref(false)

function apply(value: Domains) {
  data.value = value
  if (value.message) showToast(t(`legacy.${value.message}`), 'success')
  if (value.warning) showToast(t(`legacy.domains_${value.warning}`), 'destructive')
}
async function load() {
  try {
    apply(await api<Domains>('domains'))
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)
const errorText = (err: unknown) => {
  const code = err instanceof ApiError ? err.code : 'failed'
  const key = `legacy.domains_error_${code}`
  return t(key) === key ? t('legacy.domains_error_failed') : t(key)
}
async function send(path: string, body: unknown, method = 'POST') {
  busy.value = true
  try {
    apply(await api<Domains>(path, { method, body }))
    return ''
  } catch (err) {
    return isSignedOut(err) ? '' : errorText(err)
  } finally {
    busy.value = false
  }
}
async function act(path: string, body: unknown) {
  const error = await send(path, body)
  if (error) showToast(error, 'destructive')
}

const historyOpen = ref(false)

// ---- 站点表格 ----
const columns = computed(() => [
  { key: 'host', label: t('legacy.domains_host') },
  { key: 'target', label: t('legacy.domains_target') },
  { key: 'state', label: t('vps.modules.status') },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
const prefix = (site: Site) => (site.zone && site.host !== site.zone ? site.host.slice(0, -site.zone.length - 1) : site.host)
const siteActions = (site: Site) => [
  { key: 'details', label: t('vps.domains.details') },
  { key: 'edit', label: t('legacy.domains_edit') },
  { key: 'log', label: t('legacy.domains_access_log') },
  { key: 'toggle', label: site.enabled ? t('legacy.domains_site_disable') : t('legacy.domains_site_enable') },
  { key: 'remove', label: t('legacy.domains_remove'), danger: true },
  { key: 'remove-keep', label: t('vps.domains.removeKeepDns'), danger: true },
]
const details = ref<Site>()
const detailsOpen = computed({
  get: () => details.value !== undefined,
  set: (open) => {
    if (!open) details.value = undefined
  },
})
const detailItems = computed(() => {
  const site = details.value
  if (!site) return []
  return [
    { key: 'added', label: t('legacy.domains_added_at'), value: site.addedAt },
    { key: 'cert', label: t('legacy.domains_certificate_label'), value: site.certText },
    { key: 'dns', label: 'DNS', value: site.dnsText },
    ...(site.aliasesText ? [{ key: 'aliases', label: t('legacy.domains_aliases_short'), value: site.aliasesText }] : []),
    { key: 'access', label: t('legacy.domains_access'), value: site.accessText },
  ]
})
// 删除: 确认对话框关闭时先于 confirm 改 open, 所以要删除的站点单独保存
const removing = ref<{ host: string; removeDns: boolean }>()
const removeOpen = ref(false)
function siteAction(key: string, site: Site) {
  if (key === 'details') details.value = site
  else if (key === 'edit') openForm(site)
  else if (key === 'log') void router.push({ path: '/domains/log', query: { host: site.host } })
  else if (key === 'toggle') void act('domains/toggle', { host: site.host, enable: !site.enabled })
  else {
    removing.value = { host: site.host, removeDns: key === 'remove' }
    removeOpen.value = true
  }
}

// ---- 添加和编辑 ----
const formOpen = ref(false)
const formError = ref('')
const editing = ref<Site>()
const form = ref({
  zone: '',
  name: '',
  host: '',
  target: 'port' as 'port' | 'console',
  port: 0,
  backendTls: false,
  upstreamHost: false,
  aliases: '',
  allowIps: '',
  authUser: '',
  authPassword: '',
  authClear: false,
})
function openForm(site?: Site) {
  editing.value = site
  form.value = {
    zone: data.value?.zones?.[0] ?? '',
    name: '',
    host: '',
    target: site?.console ? 'console' : 'port',
    port: 0,
    backendTls: site?.backendTls ?? false,
    upstreamHost: site?.upstreamHost ?? false,
    aliases: (site?.aliases ?? []).join('\n'),
    allowIps: (site?.allowIps ?? []).join('\n'),
    authUser: site?.authUser ?? '',
    authPassword: '',
    authClear: false,
  }
  formError.value = ''
  formOpen.value = true
  // 编辑时填入当前端口(列表里遮住, 这里取一次)
  if (site?.hasPort) {
    api<{ value: string }>(`private-value?id=${encodeURIComponent(`domain-site:${site.host}`)}&field=target-port`)
      .then(({ value }) => (form.value.port = Number(value)))
      .catch(() => {})
  }
}
const targets = computed(() => [
  { value: 'port' as const, label: t('legacy.domains_target_port') },
  ...(data.value?.consoleTarget ? [{ value: 'console' as const, label: t('legacy.domains_target_console_short') }] : []),
])
const zoneOptions = computed(() => (data.value?.zones ?? []).map((value) => ({ value, label: value })))
const lines = (text: string) => text.split('\n').map((line) => line.trim()).filter(Boolean)
async function saveSite() {
  const value = form.value
  const body = {
    target: value.target,
    port: value.port,
    backendTls: value.backendTls,
    upstreamHost: value.upstreamHost,
    aliases: lines(value.aliases),
    allowIps: lines(value.allowIps),
    authUser: value.authUser.trim(),
    authPassword: value.authPassword,
    authClear: value.authClear,
  }
  formError.value = editing.value
    ? await send('domains/edit', { ...body, host: editing.value.host }, 'PUT')
    : await send('domains/add', { ...body, ...(data.value?.zones?.length ? { zone: value.zone, name: value.name.trim() } : { host: value.host.trim() }) })
  if (!formError.value) formOpen.value = false
}

// ---- Cloudflare 令牌 ----
const tokenName = ref('')
const tokenValue = ref('')
const TOKEN_STATES = { ok: ['success', 'legacy.domains_token_state_ok'], auth: ['destructive', 'legacy.domains_token_state_auth'], unreachable: ['warning', 'legacy.domains_token_state_unreachable'] } as const
const tokenColumns = computed(() => [
  { key: 'name', label: t('legacy.domains_token_name') },
  { key: 'state', label: t('vps.modules.status') },
  { key: 'zones', label: t('legacy.domains_zone') },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
const zonesText = (token: Token) =>
  token.zones.length ? token.zones.map((item) => `${item.zone} (${t('legacy.domains_zone_sites', { count: item.sites })})`).join(', ') : t('legacy.domains_zones_none')
async function addToken() {
  const error = await send('domains/token', { name: tokenName.value.trim(), token: tokenValue.value.trim() })
  if (error) showToast(error, 'destructive')
  else {
    tokenName.value = ''
    tokenValue.value = ''
  }
}
const removingToken = ref<Token>()
const tokenRemoveOpen = ref(false)
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('legacy.domains')" :description="t('vps.domains.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <ModuleInstall v-else-if="!data.installed" module="caddy" :name="t('legacy.domains')" @installed="load" />

    <template v-else>
      <!-- 概况 -->
      <PageSection :cols="4" :title="t('vps.domains.overview')">
        <DescriptionList
          :items="[
            { key: 'state', label: t('vps.modules.status') },
            { key: 'ipv4', label: t('legacy.domains_ipv4') },
            { key: 'ipv6', label: t('legacy.domains_ipv6') },
            { key: 'checked', label: t('legacy.domains_dns_checked'), value: data.dns?.checked, mono: true },
          ]"
        >
          <template #value-state>
            <StatusBadge :tone="data.running ? 'success' : 'warning'">{{ t(data.running ? 'legacy.node_active' : 'legacy.node_stopped') }}</StatusBadge>
          </template>
          <template v-for="family in (['ipv4', 'ipv6'] as const)" :key="family" #[`value-${family}`]>
            <PrivateValue v-if="data.dns?.[family]" :source="`domain-${family}`" field="address" :label="t(`legacy.domains_${family}`)" />
            <template v-else>—</template>
          </template>
        </DescriptionList>
        <AlertBanner v-if="data.dns?.error" tone="warning">{{ t(`legacy.domains_${data.dns.error}`) }}</AlertBanner>
        <FormActions>
          <Button v-if="data.history?.length" variant="outline" @click="historyOpen = true"><History aria-hidden="true" />{{ t('legacy.domains_history') }}</Button>
          <Button @click="openForm()"><Plus aria-hidden="true" />{{ t('legacy.domains_add') }}</Button>
        </FormActions>
      </PageSection>

      <TrafficCard feature="caddy" />

      <PageSection v-if="!data.groups?.length" :cols="4" :title="t('legacy.domains_sites')">
        <EmptyState :icon="Earth" :title="t('legacy.domains_none')" :description="t(data.zones?.length ? 'legacy.domains_add_help_zones' : 'legacy.domains_add_help_manual')" />
      </PageSection>

      <PageSection
        v-for="group in data.groups"
        :key="group.zone"
        :cols="4"
        :title="`${group.zone || t('legacy.domains_other_zone')} · ${t('legacy.domains_zone_count', { count: group.sites.length })}`"
      >
        <DataTable :columns="columns" :rows="group.sites" row-key="host" :caption="group.zone || t('legacy.domains_other_zone')" :empty="t('legacy.domains_none')">
          <template #cell-host="{ row }">
            <a :href="`https://${row.host}/`" target="_blank" rel="noopener noreferrer" class="font-medium text-primary underline">{{ group.zone ? prefix(row) : row.host }}</a>
          </template>
          <template #cell-target="{ row }">
            <template v-if="row.console">{{ t('legacy.domains_target_console') }}</template>
            <template v-else>
              {{ row.scheme }}://127.0.0.1
              <PrivateValue v-if="row.hasPort" :source="`domain-site:${row.host}`" field="target-port" :label="`${t('legacy.domains_port')} ${row.host}`" />
              <span v-if="row.options" class="text-sm text-muted-foreground">{{ row.options }}</span>
            </template>
          </template>
          <template #cell-state="{ row }">
            <InlineGroup>
              <StatusBadge v-for="badge in row.badges" :key="badge.text" :tone="badge.tone">{{ badge.text }}</StatusBadge>
            </InlineGroup>
          </template>
          <template #cell-action="{ row }">
            <ActionMenu icon-only :label="`${t('component.moreActions')} ${row.host}`" :items="siteActions(row)" @select="(key: string) => siteAction(key, row)" />
          </template>
        </DataTable>
      </PageSection>

      <!-- Cloudflare 令牌: 列表和添加表单 -->
      <CardForm @submit.prevent="addToken">
        <PageSection :cols="4" :title="t('legacy.domains_cloudflare')" :description="t('legacy.domains_token_help')">
          <DataTable v-if="data.tokens?.length" :columns="tokenColumns" :rows="data.tokens" row-key="id" :caption="t('legacy.domains_cloudflare')" :empty="t('legacy.domains_token_state_missing')">
            <template #cell-state="{ row }">
              <StatusBadge :tone="TOKEN_STATES[row.state][0]">{{ t(TOKEN_STATES[row.state][1]) }}</StatusBadge>
            </template>
            <template #cell-zones="{ row }">{{ zonesText(row) }}</template>
            <template #cell-action="{ row }">
              <ActionMenu
                icon-only
                :label="`${t('component.moreActions')} ${row.name}`"
                :items="[{ key: 'remove', label: t('legacy.domains_token_clear'), danger: true }]"
                @select="() => ((removingToken = row), (tokenRemoveOpen = true))"
              />
            </template>
          </DataTable>
          <AlertBanner v-else tone="warning">{{ t('legacy.domains_token_state_missing') }}</AlertBanner>
          <FormField v-slot="field" :label="t('legacy.domains_token_name')" :span="6">
            <Input :id="field.id" v-model="tokenName" maxlength="40" autocomplete="off" :placeholder="t('legacy.domains_token_name_placeholder')" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.domains_token')" :span="6">
            <PasswordInput :id="field.id" v-model="tokenValue" maxlength="100" autocomplete="off" spellcheck="false" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy || !tokenValue.trim()"><KeyRound aria-hidden="true" />{{ t('legacy.domains_token_save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>
    </template>

    <AppDialog v-model:open="historyOpen" :title="t('legacy.domains_history')">
      <DescriptionList :items="(data?.history ?? []).map((item, index) => ({ key: String(index), label: item.time, value: item.text }))" />
    </AppDialog>

    <AppDialog v-model:open="detailsOpen" :title="details?.host ?? ''">
      <DescriptionList :items="detailItems" />
    </AppDialog>

    <ConfirmDialog
      v-model:open="removeOpen"
      :title="t('legacy.domains_remove_confirm', { host: removing?.host ?? '' })"
      :description="removing?.removeDns ? t('vps.domains.removeWithDns') : t('vps.domains.removeKeepDnsDescription')"
      :confirm-label="t('legacy.domains_remove')"
      danger
      @confirm="removing && act('domains/remove', { host: removing.host, removeDns: removing.removeDns })"
    />
    <ConfirmDialog
      v-model:open="tokenRemoveOpen"
      :title="t('legacy.domains_token_clear')"
      :description="t('legacy.domains_token_clear_confirm', { name: removingToken?.name ?? '' })"
      :confirm-label="t('legacy.domains_token_clear')"
      danger
      @confirm="removingToken && act('domains/token/remove', { id: removingToken.id })"
    />

    <AppDialog v-model:open="formOpen" :title="editing ? `${t('legacy.domains_edit')} ${editing.host}` : t('legacy.domains_add')" :description="editing ? undefined : t(data?.zones?.length ? 'legacy.domains_add_help_zones' : 'legacy.domains_add_help_manual')">
      <AlertBanner v-if="formError" tone="destructive">{{ formError }}</AlertBanner>
      <template v-if="!editing">
        <template v-if="data?.zones?.length">
          <FormField v-slot="field" :label="t('legacy.domains_subdomain')" :span="6">
            <Input :id="field.id" v-model="form.name" maxlength="200" placeholder="nas" autocapitalize="none" spellcheck="false" autocomplete="off" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.domains_zone')" :span="6">
            <SelectMenu :id="field.id" v-model="form.zone" :options="zoneOptions" :label="t('legacy.domains_zone')" />
          </FormField>
        </template>
        <FormField v-else v-slot="field" :label="t('legacy.domains_host')">
          <Input :id="field.id" v-model="form.host" maxlength="253" placeholder="nas.example.com" autocapitalize="none" spellcheck="false" autocomplete="off" />
        </FormField>
      </template>
      <FormField :label="t('legacy.domains_target')" group :span="6">
        <SegmentedControl v-model="form.target" :options="targets" :label="t('legacy.domains_target')" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.domains_port')" :span="6">
        <NumberField :id="field.id" v-model="form.port" :min="0" :max="65535" :grouping="false" :disabled="form.target === 'console'" />
      </FormField>
      <template v-if="form.target === 'port'">
        <CheckboxField v-model="form.backendTls" :label="t('legacy.domains_backend_tls')" />
        <CheckboxField v-model="form.upstreamHost" :label="t('legacy.domains_upstream_host')" />
      </template>
      <FormField v-slot="field" :label="t('legacy.domains_aliases')" :span="6">
        <Textarea :id="field.id" v-model="form.aliases" spellcheck="false" autocapitalize="none" placeholder="www.example.com" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.domains_allow_ips')" :span="6">
        <Textarea :id="field.id" v-model="form.allowIps" spellcheck="false" placeholder="203.0.113.7" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.domains_auth_user')" :span="6" :help="t('legacy.domains_auth_help')">
        <Input :id="field.id" v-model="form.authUser" maxlength="64" autocomplete="off" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.domains_auth_password')" :span="6">
        <PasswordInput :id="field.id" v-model="form.authPassword" maxlength="128" autocomplete="new-password" :placeholder="editing?.authUser ? t('legacy.domains_auth_keep') : ''" />
      </FormField>
      <CheckboxField v-if="editing?.authUser" v-model="form.authClear" :label="t('legacy.domains_auth_clear')" />
      <template #footer>
        <Button variant="outline" @click="formOpen = false">{{ t('legacy.node_cancel') }}</Button>
        <Button :disabled="busy" @click="saveSite">{{ editing ? t('legacy.frp_save') : t('legacy.domains_add') }}</Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
