<script setup lang="ts">
import { KeyRound, Plus, ShieldCheck, Trash2 } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/app/PageHeader.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageSection from '@/components/app/PageSection.vue'
import SettingRow from '@/components/app/SettingRow.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import DataTable from '@/components/app/DataTable.vue'
import InfoTip from '@/components/app/InfoTip.vue'
import InputAction from '@/components/app/InputAction.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import { Button } from '@/components/ui/button'
import { ApiError, api } from '@/lib/api'
import { session, verifyAdmin } from '@/lib/session'
import { showToast } from '@/lib/toast'

// 安全设置: 需要服务器记录的近期管理员密码验证; 仅 IP 会话不能进入.
interface Security {
  ipAccess: { enabled: boolean; allowlist: string[] }
  securityUntil: string
}

const { t } = useI18n()
const state = ref<'loading' | 'verify' | 'ready'>('loading')
const security = ref<Security>()
const ipOnly = computed(() => session.value?.method === 'ip')

const verifyPassword = ref('')
const verifyError = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordError = ref('')
const address = ref('')
const addressError = ref('')
const busy = ref(false)

// 修改输入后清除对应的错误
watch(address, () => (addressError.value = ''))
watch([newPassword, confirmPassword], () => (passwordError.value = ''))
watch(verifyPassword, () => (verifyError.value = ''))

const addressRows = computed(() => (security.value?.ipAccess.allowlist ?? []).map((address) => ({ address })))
const addressColumns = computed(() => [
  { key: 'address', label: t('security.address'), mono: true },
  { key: 'action', label: t('security.actions'), align: 'end' as const },
])

const ipAccessEnabled = computed({
  get: () => security.value?.ipAccess.enabled ?? false,
  set: (value: boolean) => update('ip-access', 'PUT', { enabled: value }),
})

// 权限到期后回到验证
let expiryTimer: ReturnType<typeof setTimeout> | undefined
function apply(data: Security) {
  security.value = data
  state.value = 'ready'
  clearTimeout(expiryTimer)
  expiryTimer = setTimeout(expire, Math.max(0, new Date(data.securityUntil).getTime() - Date.now()))
}
function expire() {
  state.value = 'verify'
  security.value = undefined
}
onBeforeUnmount(() => clearTimeout(expiryTimer))

function errorText(err: unknown) {
  const code = err instanceof ApiError ? err.code : ''
  const known: Record<string, string> = {
    invalid_password: 'login.invalidPassword',
    too_many_attempts: 'login.tooManyAttempts',
    password_mismatch: 'security.mismatch',
    weak_password: 'security.weak',
    invalid_address: 'security.invalidAddress',
    address_not_allowed: 'security.notAllowed',
    duplicate_address: 'security.duplicate',
  }
  return t(known[code] ?? 'security.failed')
}

async function load() {
  try {
    apply(await api<Security>('security'))
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') state.value = 'verify'
    else throw err
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

// 安全设置请求: 权限过期时回到验证
async function update(path: string, method: string, body?: unknown): Promise<boolean> {
  busy.value = true
  try {
    apply(await api<Security>(`security/${path}`, { method, body }))
    return true
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') {
      expire()
      showToast(t('security.expired'))
    } else showToast(errorText(err), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

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
    expire()
    showToast(t('security.passwordChanged'), 'success')
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') expire()
    else passwordError.value = errorText(err)
  } finally {
    busy.value = false
  }
}

async function addAddress() {
  addressError.value = ''
  if (!address.value.trim()) return
  busy.value = true
  try {
    apply(await api<Security>('security/allowlist', { method: 'POST', body: { address: address.value.trim() } }))
    address.value = ''
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') expire()
    else addressError.value = errorText(err)
  } finally {
    busy.value = false
  }
}

function removeAddress(item: string) {
  update(`allowlist/${encodeURIComponent(item)}`, 'DELETE')
}
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
          <PasswordInput
            :id="field.id"
            v-model="verifyPassword"
            autocomplete="current-password"
            :aria-invalid="field.invalid"
            :aria-describedby="field.describedby"
          />
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
      <!-- 一个模块一张整行卡片: 修改密码是一个表单 -->
      <CardForm @submit.prevent="changePassword">
        <PageSection :cols="4" :title="t('security.password')" :description="t('security.passwordDescription')">
          <FormField v-slot="field" :label="t('security.newPassword')" :span="6">
            <PasswordInput :id="field.id" v-model="newPassword" autocomplete="new-password" />
          </FormField>
          <FormField v-slot="field" :label="t('security.confirmPassword')" :error="passwordError" :span="6">
            <PasswordInput
              :id="field.id"
              v-model="confirmPassword"
              autocomplete="new-password"
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

      <!-- IP 访问模块: 开关, 白名单表格, 添加地址 -->
      <CardForm @submit.prevent="addAddress">
        <PageSection :cols="4" :title="t('security.ipAccess')" :description="t('security.ipAccessDescription')">
          <template #info>
            <InfoTip :label="t('security.ipRangesLabel')" :text="t('security.ipRanges')" />
          </template>
          <SwitchField v-model="ipAccessEnabled" :label="t('security.enableIpAccess')" :disabled="busy" />
          <DataTable
            :columns="addressColumns"
            :rows="addressRows"
            row-key="address"
            :caption="t('security.allowlistTitle')"
            :empty="t('security.empty')"
          >
            <template #cell-action="{ row }">
              <Button
                variant="outline"
                size="sm"
                :disabled="busy"
                :aria-label="t('security.removeLabel', { address: String(row.address) })"
                @click="removeAddress(String(row.address))"
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
              inputmode="decimal"
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
    </template>
  </CardGrid>
</template>
