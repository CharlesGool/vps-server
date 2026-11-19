<script setup lang="ts">
import { BadgePlus, Download, KeyRound, LogOut, Plus, Send, ShieldCheck, Trash2 } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import CheckboxField from '@/components/app/CheckboxField.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import CopyField from '@/components/app/CopyField.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import GroupBlock from '@/components/app/GroupBlock.vue'
import InfoTip from '@/components/app/InfoTip.vue'
import InputAction from '@/components/app/InputAction.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import RadioField from '@/components/app/RadioField.vue'
import SettingRow from '@/components/app/SettingRow.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { session, verifyAdmin } from '@/lib/session'
import { showToast } from '@/lib/toast'

// 安全设置: 需要服务器记录的近期管理员密码验证; 仅 IP 会话不能进入. 每次修改服务器都返回整页状态.
interface DownloadFile {
  system?: string
  name: string
  type: string
  data: string
}
interface Security {
  securityUntil: string
  notice?: string
  ipAccess: { enabled: boolean; allowlist: string[]; loadError: boolean }
  certificates: {
    mode: string
    modes: string[]
    current: { name: string; serial: string } | null
    currentSetup: DownloadFile[]
    items: { name: string; serial: string; created: number; revoked: boolean }[]
  }
  loginBan: {
    enabled: boolean
    loadError: boolean
    window: number
    maxAttempts: number
    lockout: number
    lockoutMax: number
    globalMaxAttempts: number
    globalLockout: number
    globalState: 'normal' | 'flagged' | 'banned'
    globalRemaining: number
    sources: { ip: string; state: 'normal' | 'flagged' | 'banned'; remaining: number; recent: number; total: number; triggered: number; last: number }[]
  }
  consoleAccess: { enabled: boolean; loadError: boolean; networks: string[]; current: string; currentListed: boolean; recovery: string }
  sessions: {
    ttl: number
    idle: number
    items: { id: string; current: boolean; ip: string; method: string; device: string; created: number; seen: number }[]
  }
  alerts: { server: string; configured: boolean; newIp: boolean; ban: boolean; loadError: boolean }
  audit: { event: string; ip?: string; detail?: string; t: number }[]
  issued?: { name: string; serial: string; password: string; bundle: DownloadFile; setup: DownloadFile[] }
}

const { t, locale } = useI18n()
const router = useRouter()
const state = ref<'loading' | 'verify' | 'ready'>('loading')
const security = ref<Security>()
const ipOnly = computed(() => session.value?.method === 'ip')
const busy = ref(false)

const verifyPassword = ref('')
const verifyError = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordError = ref('')
const address = ref('')
const addressError = ref('')
const certName = ref('')
const certError = ref('')
const loginMode = ref('either')
const modeError = ref('')
const network = ref('')
const networkError = ref('')
const alertServer = ref('')
const alertKey = ref('')
const alertNewIp = ref(false)
const alertBan = ref(false)
const alertError = ref('')
const auditPage = ref(1)
const issued = ref<Security['issued']>()
const issuedOpen = ref(false)

watch(address, () => (addressError.value = ''))
watch([newPassword, confirmPassword], () => (passwordError.value = ''))
watch(verifyPassword, () => (verifyError.value = ''))
watch(certName, () => (certError.value = ''))
watch(network, () => (networkError.value = ''))

// ---- 格式化 ----
const dateTime = computed(() => new Intl.DateTimeFormat(locale.value, { dateStyle: 'short', timeStyle: 'medium' }))
const time = (seconds: number) => dateTime.value.format(new Date(seconds * 1000))
const date = (seconds: number) => new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(seconds * 1000))
function duration(seconds: number) {
  if (seconds >= 3600) return t('legacy.security_hours', { count: seconds % 3600 === 0 ? seconds / 3600 : Math.round(seconds / 360) / 10 })
  if (seconds >= 60 && seconds % 60 === 0) return t('legacy.security_minutes', { count: seconds / 60 })
  return t('legacy.security_seconds', { count: seconds })
}
const fileHref = (file: DownloadFile) => `data:${file.type};base64,${file.data}`

// ---- 状态 ----
let expiryTimer: ReturnType<typeof setTimeout> | undefined
function apply(data: Security) {
  security.value = data
  loginMode.value = data.certificates.mode
  alertServer.value = data.alerts.server
  alertNewIp.value = data.alerts.newIp
  alertBan.value = data.alerts.ban
  state.value = 'ready'
  clearTimeout(expiryTimer)
  expiryTimer = setTimeout(expire, Math.max(0, new Date(data.securityUntil).getTime() - Date.now()))
}
function expire() {
  state.value = 'verify'
  security.value = undefined
}
onBeforeUnmount(() => clearTimeout(expiryTimer))

// 服务器返回的错误代码: 模板的通用代码用 security.*, 其余沿用控制台原有的提示(legacy.*)
const ERRORS: Record<string, string> = {
  invalid_password: 'login.invalidPassword',
  password_mismatch: 'security.mismatch',
  weak_password: 'vps.security.weakPassword',
  invalid_address: 'security.invalidAddress',
  address_not_allowed: 'security.notAllowed',
  duplicate_address: 'security.duplicate',
  allowlist_full: 'vps.security.allowlistFull',
}
function errorText(err: unknown) {
  if (err instanceof ApiError && err.code === 'too_many_attempts') return t('login.tooManyAttempts', { seconds: Number(err.data.retryAfter ?? 0) })
  const code = err instanceof ApiError ? err.code : ''
  if (ERRORS[code]) return t(ERRORS[code]!)
  if (code && t(`legacy.${code}`) !== `legacy.${code}`) return t(`legacy.${code}`)
  return t('security.failed')
}

async function load() {
  try {
    apply(await api<Security>('security'))
  } catch (err) {
    if (err instanceof ApiError && (err.code === 'security_required' || err.code === 'password_session_required')) state.value = 'verify'
    else if (!isSignedOut(err)) showToast(t('security.failed'), 'destructive')
  }
}
onMounted(load)

async function verify() {
  if (busy.value || !verifyPassword.value) return
  busy.value = true
  verifyError.value = ''
  try {
    await verifyAdmin(verifyPassword.value)
    verifyPassword.value = ''
    await load()
  } catch (err) {
    verifyError.value = errorText(err)
  } finally {
    busy.value = false
  }
}

// 安全设置请求: 成功时应用新状态; 权限过期时回到验证; 失败时把错误交给 onError(没有时用 Toast)
async function update(path: string, method: string, body?: unknown, onError?: (message: string) => void): Promise<Security | undefined> {
  busy.value = true
  try {
    const data = await api<Security>(`security/${path}`, { method, body })
    apply(data)
    return data
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') {
      expire()
      showToast(t('security.expired'))
    } else if (onError) onError(errorText(err))
    else showToast(errorText(err), 'destructive')
    return undefined
  } finally {
    busy.value = false
  }
}

// ---- 管理员密码: 修改后所有会话(包括这一个)结束, 回到登录页 ----
async function changePassword() {
  passwordError.value = ''
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = t('security.mismatch')
    return
  }
  busy.value = true
  try {
    await api('security/password', { method: 'PUT', body: { password: newPassword.value, confirm: confirmPassword.value } })
    newPassword.value = confirmPassword.value = ''
    showToast(t('vps.security.passwordChanged'), 'success')
    if (session.value) session.value = { ...session.value, authenticated: false, method: undefined, securityUntil: undefined }
    await router.push({ name: 'login' })
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') expire()
    else passwordError.value = errorText(err)
  } finally {
    busy.value = false
  }
}

// ---- IP 免密登录 ----
const ipAccessEnabled = computed({
  get: () => security.value?.ipAccess.enabled ?? false,
  set: (value: boolean) => void update('ip-access', 'PUT', { enabled: value }),
})
const addressRows = computed(() => (security.value?.ipAccess.allowlist ?? []).map((item) => ({ address: item })))
const addressColumns = computed(() => [
  { key: 'address', label: t('security.address'), mono: true },
  { key: 'action', label: t('security.actions'), align: 'end' as const },
])
async function addAddress() {
  if (!address.value.trim()) return
  if (await update('allowlist', 'POST', { address: address.value.trim() }, (message) => (addressError.value = message))) address.value = ''
}

// ---- 登录方式和客户端证书 ----
const modeOptions = computed(() =>
  (security.value?.certificates.modes ?? []).map((value) => ({ value, label: t(`legacy.login_mode_${value}`), description: t(`legacy.login_mode_${value}_help`) })),
)
async function saveMode() {
  modeError.value = ''
  if (await update('login-mode', 'PUT', { mode: loginMode.value }, (message) => (modeError.value = message))) showToast(t('legacy.login_mode_saved'), 'success')
}
const certRows = computed(() =>
  (security.value?.certificates.items ?? []).map((item) => ({ ...item, serialShort: item.serial.slice(0, 8), createdText: date(item.created) })),
)
const certColumns = computed(() => [
  { key: 'name', label: t('legacy.client_cert_name') },
  { key: 'serialShort', label: t('vps.security.serial'), mono: true },
  { key: 'createdText', label: t('vps.security.created') },
  { key: 'action', label: t('security.actions'), align: 'end' as const },
])
async function issueCert() {
  if (!certName.value.trim()) return
  const data = await update('certificates', 'POST', { name: certName.value.trim() }, (message) => (certError.value = message))
  if (data?.issued) {
    certName.value = ''
    issued.value = data.issued
    issuedOpen.value = true
  }
}
function revokeCert(serial: string) {
  void update('certificates/revoke', 'POST', { serial })
}

// ---- 登录失败封禁 ----
const loginBanEnabled = computed({
  get: () => security.value?.loginBan.enabled ?? false,
  set: (value: boolean) => void update('login-ban', 'PUT', { enabled: value }),
})
const banRows = computed(() =>
  (security.value?.loginBan.sources ?? []).map((row) => ({
    ...row,
    counts: t('legacy.login_ban_counts', { recent: row.recent, total: row.total, triggered: row.triggered }),
    lastText: time(row.last),
  })),
)
const banColumns = computed(() => [
  { key: 'ip', label: t('security.address'), mono: true },
  { key: 'state', label: t('vps.security.state') },
  { key: 'counts', label: t('vps.security.attempts') },
  { key: 'lastText', label: t('vps.security.lastAttempt') },
])
const banRule = computed(() => {
  const ban = security.value?.loginBan
  return ban ? t('legacy.login_ban_rule', { window: ban.window, count: ban.maxAttempts, first: duration(ban.lockout), max: duration(ban.lockoutMax) }) : ''
})
const globalRule = computed(() => {
  const ban = security.value?.loginBan
  return ban && ban.globalMaxAttempts > 0
    ? t('legacy.login_global_rule', { window: ban.window, count: ban.globalMaxAttempts, duration: duration(ban.globalLockout) })
    : ''
})

// ---- 控制台访问限制 ----
const consoleAccessEnabled = computed({
  get: () => security.value?.consoleAccess.enabled ?? false,
  set: (value: boolean) => void update('console-access', 'PUT', { enabled: value }),
})
const networkRows = computed(() => (security.value?.consoleAccess.networks ?? []).map((item) => ({ network: item })))
const networkColumns = computed(() => [
  { key: 'network', label: t('vps.security.network'), mono: true },
  { key: 'action', label: t('security.actions'), align: 'end' as const },
])
async function addNetwork(value = network.value.trim()) {
  if (!value) return
  if (await update('console-access/add', 'POST', { network: value }, (message) => (networkError.value = message))) network.value = ''
}

// ---- 登录设备 ----
const sessionsIntro = computed(() => {
  const s = security.value?.sessions
  if (!s) return ''
  return s.idle > 0 ? t('legacy.sessions_intro', { ttl: duration(s.ttl), idle: duration(s.idle) }) : t('legacy.sessions_intro_no_idle', { ttl: duration(s.ttl) })
})
const sessionRows = computed(() =>
  (security.value?.sessions.items ?? []).map((row) => ({
    ...row,
    deviceText: row.device || t('legacy.sessions_unknown_device'),
    methodText: t(`legacy.sessions_method_${row.method}`),
    createdText: time(row.created),
    seenText: time(row.seen),
  })),
)
const sessionColumns = computed(() => [
  { key: 'deviceText', label: t('vps.security.device') },
  { key: 'methodText', label: t('vps.security.method') },
  { key: 'ip', label: t('security.address'), mono: true },
  { key: 'createdText', label: t('vps.security.signedIn') },
  { key: 'seenText', label: t('vps.security.lastSeen') },
  { key: 'action', label: t('security.actions'), align: 'end' as const },
])
const sessionPage = ref(1)
const sessionPageRows = computed(() => sessionRows.value.slice((sessionPage.value - 1) * 10, sessionPage.value * 10))
const hasOtherSessions = computed(() => (security.value?.sessions.items ?? []).some((row) => !row.current))

// ---- Bark 提醒 ----
async function saveAlerts() {
  alertError.value = ''
  const ok = await update(
    'alerts',
    'PUT',
    { server: alertServer.value, key: alertKey.value, newIp: alertNewIp.value, ban: alertBan.value },
    (message) => (alertError.value = message),
  )
  if (ok) {
    alertKey.value = ''
    showToast(t('legacy.alerts_saved'), 'success')
  }
}
async function testAlerts() {
  if (await update('alerts/test', 'POST')) showToast(t('legacy.alerts_test_sent'), 'success')
}

// ---- 安全记录: 每页 10 条 ----
const auditRows = computed(() =>
  (security.value?.audit ?? []).map((entry, index) => {
    const detail = String(entry.detail ?? '')
    const banned = ['ban', 'global_ban', 'ban_observed', 'global_ban_observed'].includes(entry.event) && /^\d+$/.test(detail)
    const method = `legacy.sessions_method_${detail}`
    return {
      id: index,
      eventText: t(`legacy.audit_${entry.event}`) === `legacy.audit_${entry.event}` ? entry.event : t(`legacy.audit_${entry.event}`),
      ip: entry.ip ?? '',
      detailText: banned ? duration(Number(detail)) : detail && t(method) !== method ? t(method) : detail,
      timeText: time(entry.t),
    }
  }),
)
const auditPageRows = computed(() => auditRows.value.slice((auditPage.value - 1) * 10, auditPage.value * 10))
const auditColumns = computed(() => [
  { key: 'eventText', label: t('vps.security.event') },
  { key: 'ip', label: t('security.address'), mono: true },
  { key: 'detailText', label: t('vps.security.detail') },
  { key: 'timeText', label: t('vps.security.time') },
])
</script>

<template>
  <CardGrid>
    <PageHeader
      :title="t('page.security')"
      :description="ipOnly ? undefined : state === 'verify' ? t('security.verifyDescription') : undefined"
      :trail="[{ to: '/settings', label: t('page.settings') }]"
    />

    <PageSection v-if="ipOnly" :cols="2" :col="2" :title="t('security.verifyTitle')" :description="t('security.ipSession')" />

    <!-- 验证: 居中的窄卡片, 和登录卡一样 -->
    <CardForm v-else-if="state === 'verify'" @submit.prevent="verify">
      <PageSection :cols="2" :col="2" :title="t('security.verifyTitle')">
        <FormField v-slot="field" :label="t('security.adminPassword')" :error="verifyError">
          <PasswordInput :id="field.id" v-model="verifyPassword" autocomplete="current-password" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
        </FormField>
        <FormActions>
          <Button type="submit" :disabled="busy || !verifyPassword">
            <ShieldCheck aria-hidden="true" />
            {{ t('security.verify') }}
          </Button>
        </FormActions>
      </PageSection>
    </CardForm>

    <template v-else-if="state === 'ready' && security">
      <!-- IP 免密登录: 开关, 白名单表格, 添加地址 -->
      <CardForm @submit.prevent="addAddress">
        <PageSection :cols="4" :title="t('security.ipAccess')" :description="t('security.ipAccessDescription')">
          <template #info>
            <InfoTip :label="t('security.ipRangesLabel')" :text="t('security.ipRanges')" />
          </template>
          <AlertBanner v-if="security.ipAccess.loadError" tone="destructive">{{ t('legacy.access_load_error') }}</AlertBanner>
          <SwitchField v-model="ipAccessEnabled" :label="t('security.enableIpAccess')" :disabled="busy" />
          <DataTable :columns="addressColumns" :rows="addressRows" row-key="address" :caption="t('security.allowlistTitle')" :empty="t('security.empty')">
            <template #cell-action="{ row }">
              <Button
                variant="outline"
                size="sm"
                :disabled="busy"
                :aria-label="t('security.removeLabel', { address: String(row.address) })"
                @click="update('allowlist/remove', 'POST', { address: String(row.address) })"
              >
                <Trash2 aria-hidden="true" />
                {{ t('security.remove') }}
              </Button>
            </template>
          </DataTable>
          <SettingRow v-slot="field" :label="t('security.address')" :description="t('security.addTitle')" :error="addressError">
            <InputAction
              :id="field.id"
              v-model="address"
              autocomplete="off"
              spellcheck="false"
              placeholder="192.168.1.20"
              :aria-invalid="field.invalid"
              :aria-describedby="field.describedby"
              :action-label="t('security.add')"
              :action-icon="Plus"
              :action-disabled="busy || !address.trim()"
            />
          </SettingRow>
        </PageSection>
      </CardForm>

      <!-- 登录方式: 单选组和保存 -->
      <CardForm @submit.prevent="saveMode">
        <PageSection :cols="4" :title="t('vps.security.loginMethod')" :description="t('legacy.login_mode_hint')">
          <!-- 卡片标题已经是"登录方式", 单选组的标签只给读屏 -->
          <FormField :label="t('legacy.login_mode_title')" group hide-label :error="modeError">
            <RadioField v-model="loginMode" :options="modeOptions" :label="t('legacy.login_mode_title')" :disabled="busy" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy || loginMode === security.certificates.mode">{{ t('legacy.login_mode_save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <!-- 客户端证书: 当前连接的证书, 证书列表, 签发 -->
      <CardForm @submit.prevent="issueCert">
        <PageSection :cols="4" :title="t('legacy.access_client_cert')" :description="t('legacy.client_cert_intro')">
          <AlertBanner v-if="security.certificates.current" tone="success">
            {{ t('legacy.client_cert_current_ok', { name: security.certificates.current.name }) }}
          </AlertBanner>
          <AlertBanner v-else tone="info" :title="t('legacy.client_cert_current_none')">{{ t('legacy.client_cert_current_none_hint') }}</AlertBanner>
          <GroupBlock v-if="security.certificates.currentSetup.length" :title="t('legacy.client_cert_autoselect')">
            <p class="text-sm text-muted-foreground">{{ t('legacy.client_cert_autoselect_help') }}</p>
            <FormActions align="start">
              <Button v-for="file in security.certificates.currentSetup" :key="file.name" as-child variant="outline">
                <a :href="fileHref(file)" :download="file.name" :title="t(`legacy.client_cert_setup_${file.system}`)">
                  <Download aria-hidden="true" />{{ t(`legacy.client_cert_setup_label_${file.system}`) }}
                </a>
              </Button>
            </FormActions>
          </GroupBlock>
          <DataTable :columns="certColumns" :rows="certRows" row-key="serial" :caption="t('legacy.access_client_cert')" :empty="t('legacy.client_cert_list_empty')">
            <template #cell-action="{ row }">
              <StatusBadge v-if="row.revoked">{{ t('legacy.client_cert_revoked') }}</StatusBadge>
              <ConfirmDialog
                v-else
                :title="t('vps.security.revokeTitle', { name: String(row.name) })"
                :description="t('vps.security.revokeDescription')"
                :confirm-label="t('legacy.client_cert_revoke')"
                danger
                @confirm="revokeCert(String(row.serial))"
              >
                <template #trigger>
                  <Button variant="outline" size="sm" :disabled="busy">
                    <Trash2 aria-hidden="true" />
                    {{ t('legacy.client_cert_revoke') }}
                  </Button>
                </template>
              </ConfirmDialog>
            </template>
          </DataTable>
          <SettingRow v-slot="field" :label="t('legacy.client_cert_name')" :description="t('vps.security.issueDescription')" :error="certError">
            <InputAction
              :id="field.id"
              v-model="certName"
              maxlength="40"
              autocomplete="off"
              :aria-invalid="field.invalid"
              :aria-describedby="field.describedby"
              :action-label="t('legacy.client_cert_issue')"
              :action-icon="BadgePlus"
              :action-disabled="busy || !certName.trim()"
            />
          </SettingRow>
        </PageSection>
      </CardForm>

      <!-- 登录失败封禁 -->
      <PageSection :cols="4" :title="t('legacy.login_ban_heading')" :description="banRule">
        <AlertBanner v-if="security.loginBan.loadError" tone="destructive">{{ t('legacy.login_ban_load_error') }}</AlertBanner>
        <AlertBanner v-if="security.loginBan.globalState !== 'normal'" :tone="security.loginBan.globalState === 'banned' ? 'destructive' : 'warning'">
          {{ t(security.loginBan.globalState === 'banned' ? 'legacy.login_global_active' : 'legacy.login_global_flagged', { seconds: security.loginBan.globalRemaining }) }}
        </AlertBanner>
        <p v-if="globalRule" class="text-sm text-muted-foreground">{{ globalRule }}</p>
        <SwitchField v-model="loginBanEnabled" :label="t('legacy.login_ban_switch')" :description="t('legacy.login_ban_observe_hint')" :disabled="busy" />
        <DataTable :columns="banColumns" :rows="banRows" row-key="ip" :caption="t('legacy.login_ban_heading')" :empty="t('legacy.login_ban_empty')">
          <template #cell-state="{ row }">
            <StatusBadge v-if="row.state === 'banned'" tone="destructive">{{ t('legacy.login_ban_state_banned', { seconds: row.remaining }) }}</StatusBadge>
            <StatusBadge v-else-if="row.state === 'flagged'" tone="warning">{{ t('legacy.login_ban_state_flagged', { seconds: row.remaining }) }}</StatusBadge>
            <StatusBadge v-else>{{ t('legacy.login_ban_state_normal') }}</StatusBadge>
          </template>
        </DataTable>
        <FormActions>
          <ConfirmDialog
            :title="t('legacy.login_ban_clear')"
            :description="t('vps.security.clearBanDescription')"
            :confirm-label="t('legacy.login_ban_clear')"
            danger
            @confirm="update('login-ban/clear', 'POST')"
          >
            <template #trigger>
              <Button variant="destructive" :disabled="busy || !banRows.length">{{ t('legacy.login_ban_clear') }}</Button>
            </template>
          </ConfirmDialog>
        </FormActions>
      </PageSection>

      <!-- 控制台访问限制 -->
      <CardForm @submit.prevent="addNetwork()">
        <PageSection :cols="4" :title="t('legacy.console_access_heading')" :description="t('legacy.console_access_intro')">
          <AlertBanner v-if="security.consoleAccess.loadError" tone="destructive">{{ t('legacy.console_access_load_error') }}</AlertBanner>
          <AlertBanner :tone="security.consoleAccess.currentListed ? 'success' : 'info'">
            {{
              t('legacy.console_access_current', {
                ip: security.consoleAccess.current,
                state: t(security.consoleAccess.currentListed ? 'legacy.console_access_listed' : 'legacy.console_access_unlisted'),
              })
            }}
          </AlertBanner>
          <SwitchField v-model="consoleAccessEnabled" :label="t('legacy.console_access_switch')" :disabled="busy" />
          <DataTable :columns="networkColumns" :rows="networkRows" row-key="network" :caption="t('legacy.console_access_heading')" :empty="t('legacy.console_access_empty')">
            <template #cell-action="{ row }">
              <Button
                variant="outline"
                size="sm"
                :disabled="busy"
                :aria-label="t('security.removeLabel', { address: String(row.network) })"
                @click="update('console-access/remove', 'POST', { network: String(row.network) })"
              >
                <Trash2 aria-hidden="true" />
                {{ t('security.remove') }}
              </Button>
            </template>
          </DataTable>
          <SettingRow v-slot="field" :label="t('vps.security.network')" :description="t('vps.security.networkDescription')" :error="networkError">
            <InputAction
              :id="field.id"
              v-model="network"
              autocomplete="off"
              spellcheck="false"
              placeholder="203.0.113.5 / 198.51.100.0/24"
              :aria-invalid="field.invalid"
              :aria-describedby="field.describedby"
              :action-label="t('vps.security.addNetwork')"
              :action-icon="Plus"
              :action-disabled="busy || !network.trim()"
            />
          </SettingRow>
          <SettingRow v-if="!security.consoleAccess.currentListed" :label="t('legacy.console_access_add_current')" :description="security.consoleAccess.current" group>
            <FormActions>
              <Button type="button" variant="outline" :disabled="busy" @click="addNetwork(security.consoleAccess.current)">{{ t('legacy.console_access_add_current') }}</Button>
            </FormActions>
          </SettingRow>
          <SettingRow v-slot="field" :label="t('vps.security.recovery')" :description="t('legacy.console_access_recovery')">
            <CopyField :id="field.id" :value="security.consoleAccess.recovery" />
          </SettingRow>
        </PageSection>
      </CardForm>

      <!-- 登录设备 -->
      <PageSection :cols="4" :title="t('legacy.sessions_heading')" :description="sessionsIntro">
        <DataTable :columns="sessionColumns" :rows="sessionPageRows" row-key="id" :caption="t('legacy.sessions_heading')" :empty="t('legacy.sessions_empty')">
          <template #cell-deviceText="{ row }">
            {{ row.deviceText }}
            <StatusBadge v-if="row.current" tone="info">{{ t('legacy.sessions_current') }}</StatusBadge>
          </template>
          <template #cell-action="{ row }">
            <Button v-if="!row.current" variant="outline" size="sm" :disabled="busy" @click="update('sessions/revoke', 'POST', { id: String(row.id) })">
              <LogOut aria-hidden="true" />
              {{ t('legacy.sessions_revoke') }}
            </Button>
          </template>
        </DataTable>
        <PaginationBar v-if="sessionRows.length > 10" v-model="sessionPage" :total="sessionRows.length" />
        <FormActions v-if="hasOtherSessions">
          <ConfirmDialog
            :title="t('legacy.sessions_revoke_others')"
            :description="t('vps.security.revokeOthersDescription')"
            :confirm-label="t('legacy.sessions_revoke_others')"
            danger
            @confirm="update('sessions/revoke-others', 'POST')"
          >
            <template #trigger>
              <Button variant="destructive" :disabled="busy">{{ t('legacy.sessions_revoke_others') }}</Button>
            </template>
          </ConfirmDialog>
        </FormActions>
      </PageSection>

      <!-- Bark 提醒: 一个表单 -->
      <CardForm @submit.prevent="saveAlerts">
        <PageSection :cols="4" :title="t('legacy.alerts_heading')" :description="t('legacy.alerts_intro')">
          <AlertBanner v-if="security.alerts.loadError" tone="destructive">{{ t('legacy.alerts_load_error') }}</AlertBanner>
          <AlertBanner :tone="security.alerts.configured ? 'success' : 'info'">
            {{ t(security.alerts.configured ? 'legacy.alerts_status_on' : 'legacy.alerts_status_off') }}
          </AlertBanner>
          <FormField v-slot="field" :label="t('legacy.alerts_server')" :span="6">
            <Input :id="field.id" v-model="alertServer" maxlength="200" spellcheck="false" autocomplete="off" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.alerts_key')" :span="6" :error="alertError">
            <PasswordInput
              :id="field.id"
              v-model="alertKey"
              maxlength="128"
              autocomplete="off"
              :placeholder="security.alerts.configured ? t('legacy.alerts_key_keep') : ''"
              :aria-invalid="field.invalid"
              :aria-describedby="field.describedby"
            />
          </FormField>
          <CheckboxField v-model="alertNewIp" :label="t('legacy.alerts_on_new_ip')" :span="6" />
          <CheckboxField v-model="alertBan" :label="t('legacy.alerts_on_ban')" :span="6" />
          <FormActions>
            <ConfirmDialog
              v-if="security.alerts.configured"
              :title="t('legacy.alerts_clear_key')"
              :description="t('vps.security.clearKeyDescription')"
              :confirm-label="t('legacy.alerts_clear_key')"
              danger
              @confirm="update('alerts/clear-key', 'POST')"
            >
              <template #trigger>
                <Button type="button" variant="destructive" :disabled="busy">{{ t('legacy.alerts_clear_key') }}</Button>
              </template>
            </ConfirmDialog>
            <Button v-if="security.alerts.configured" type="button" variant="outline" :disabled="busy" @click="testAlerts">
              <Send aria-hidden="true" />{{ t('legacy.alerts_test') }}
            </Button>
            <Button type="submit" :disabled="busy || !alertServer.trim()">{{ t('legacy.alerts_save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <!-- 安全记录: 最近 50 条, 每页 10 条 -->
      <PageSection :cols="4" :title="t('legacy.audit_heading')" :description="t('legacy.audit_intro')">
        <DataTable :columns="auditColumns" :rows="auditPageRows" row-key="id" :caption="t('legacy.audit_heading')" :empty="t('legacy.audit_empty')" />
        <PaginationBar v-if="auditRows.length > 10" v-model="auditPage" :total="auditRows.length" />
      </PageSection>

      <!-- 管理员密码: 修改后所有会话结束 -->
      <CardForm @submit.prevent="changePassword">
        <PageSection :cols="4" :title="t('security.password')" :description="t('vps.security.passwordDescription')">
          <FormField v-slot="field" :label="t('security.newPassword')" :span="6">
            <PasswordInput :id="field.id" v-model="newPassword" autocomplete="new-password" maxlength="128" />
          </FormField>
          <FormField v-slot="field" :label="t('security.confirmPassword')" :error="passwordError" :span="6">
            <PasswordInput
              :id="field.id"
              v-model="confirmPassword"
              autocomplete="new-password"
              maxlength="128"
              :aria-invalid="field.invalid"
              :aria-describedby="field.describedby"
            />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy || !newPassword || !confirmPassword">
              <KeyRound aria-hidden="true" />
              {{ t('security.savePassword') }}
            </Button>
          </FormActions>
        </PageSection>
      </CardForm>
    </template>

    <!-- 刚签发的证书: 证书包密码只显示这一次 -->
    <AppDialog v-if="issued" v-model:open="issuedOpen" :title="t('legacy.client_cert_issued_heading')" :description="t('legacy.client_cert_issued_text')">
      <FormField v-slot="field" :label="t('legacy.client_cert_password')">
        <CopyField :id="field.id" :value="issued.password" />
      </FormField>
      <GroupBlock :title="t('legacy.client_cert_steps_title')">
        <ol class="list-decimal pl-6 text-sm">
          <li>{{ t('legacy.client_cert_step_setup') }}</li>
          <li>{{ t('legacy.client_cert_step_restart') }}</li>
          <li>{{ t('legacy.client_cert_step_verify') }}</li>
        </ol>
      </GroupBlock>
      <FormActions v-if="issued.setup.length" align="start">
        <Button v-for="file in issued.setup" :key="file.name" as-child variant="outline">
          <a :href="fileHref(file)" :download="file.name" :title="t(`legacy.client_cert_setup_${file.system}`)">
            <Download aria-hidden="true" />{{ t(`legacy.client_cert_setup_label_${file.system}`) }}
          </a>
        </Button>
      </FormActions>
      <GroupBlock :title="t('legacy.client_cert_manual')">
        <p class="text-sm">{{ t('legacy.client_cert_step_download') }}</p>
        <p class="text-sm">{{ t('legacy.client_cert_step_import') }}</p>
        <ul class="list-disc pl-6 text-sm text-muted-foreground">
          <li v-for="system in ['windows', 'macos', 'android', 'ios', 'firefox']" :key="system">{{ t(`legacy.client_cert_os_${system}`) }}</li>
        </ul>
      </GroupBlock>
      <template #footer>
        <Button as-child variant="outline">
          <a :href="fileHref(issued.bundle)" :download="issued.bundle.name"><Download aria-hidden="true" />{{ t('legacy.client_cert_download') }}</a>
        </Button>
        <Button type="button" @click="issuedOpen = false">{{ t('vps.common.done') }}</Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
