<script setup lang="ts">
import { ArchiveRestore, Eye } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import CheckboxField from '@/components/app/CheckboxField.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import { Button } from '@/components/ui/button'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { useSecurePage } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// 恢复备份: 先看再确认. 加密备份先输入私钥查看内容; 能看到内容后显示来源主机, 版本等, 有风险(来自别的主机或更新的版本)时要勾选确认.
// 私钥只随这次请求发送, 不保存. 和备份页一样, 进入前要验证管理员密码(useSecurePage); 验证后重新查看, 已输入的私钥保留.
interface Info {
  name: string
  sealed: boolean
  readable: boolean
  keyMatch: boolean | null
  host: string | null
  version: string | null
  kind: string | null
  created: string | null
  files: number | null
  sameHost: boolean | null
  newer: boolean | null
  risky: boolean
}
const KINDS: Record<string, string> = { manual: 'manual', scheduled: 'scheduled', 'pre-upgrade': 'pre_upgrade', 'pre-restore': 'pre_restore' }

const { t } = useI18n()
const { state } = useSecurePage()
const route = useRoute()
const router = useRouter()
const name = computed(() => (typeof route.query.name === 'string' ? route.query.name : ''))
const info = ref<Info>()
const key = ref('')
const ack = ref(false)
const busy = ref(false)
const error = ref('')

const errorText = (err: unknown) => {
  const code = err instanceof ApiError ? err.code : 'failed'
  const text = t(`console.backup_error_${code}`)
  return text === `console.backup_error_${code}` ? t('console.backup_error_failed') : text
}
// 验证过期(security_required)或 IP 免密会话: 回到验证卡片, 和 useSecurePage 的 guard 相同
function expired(err: unknown) {
  if (!(err instanceof ApiError) || (err.code !== 'security_required' && err.code !== 'password_session_required')) return false
  state.value = err.code === 'security_required' ? 'verify' : 'ip'
  return true
}
async function inspect(withKey = false) {
  busy.value = true
  error.value = ''
  try {
    info.value = await api<Info>('backup/inspect', { method: 'POST', body: { name: name.value, privateKey: withKey ? key.value : '' } })
    state.value = 'ready'
  } catch (err) {
    if (expired(err)) return
    if (err instanceof ApiError && err.code === 'not_found') {
      showToast(t('console.backup_error_not_found'), 'destructive')
      return router.replace('/backup')
    }
    if (!isSignedOut(err)) error.value = errorText(err)
  } finally {
    busy.value = false
  }
}
// 没有指定备份(直接打开这个地址)时只说明从备份列表选择
onMounted(() => {
  if (name.value) void inspect()
})

const details = computed(() => {
  const value = info.value
  if (!value?.readable) return []
  return [
    { key: 'host', label: t('console.backup_restore_host'), value: value.host || '?' },
    { key: 'version', label: t('console.backup_restore_version'), value: value.version || '?' },
    { key: 'kind', label: t('console.backup_restore_kind'), value: value.kind && KINDS[value.kind] ? t(`console.backup_kind_${KINDS[value.kind]}`) : (value.kind ?? '') },
    { key: 'created', label: t('console.backup_restore_created'), value: value.created ?? '—' },
    { key: 'files', label: t('console.backup_restore_files'), value: String(value.files ?? 0) },
  ]
})
async function restore() {
  busy.value = true
  error.value = ''
  try {
    await api('backup/restore', { method: 'POST', body: { name: name.value, privateKey: key.value, ack: ack.value } })
    showToast(t('console.backup_msg_restore_started'), 'success')
    await router.push('/backup')
  } catch (err) {
    if (!isSignedOut(err) && !expired(err)) error.value = errorText(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.backup_restore_title')" :description="name" :trail="[{ to: '/backup', label: t('console.backup') }]" />

    <PageSection v-if="!name" :cols="4" :title="t('console.backup_restore_title')">
      <EmptyState :icon="ArchiveRestore" :title="t('vps.backup.pick')" />
      <FormActions>
        <Button as-child variant="outline">
          <RouterLink to="/backup">{{ t('console.backup_list') }}</RouterLink>
        </Button>
      </FormActions>
    </PageSection>

    <AdminVerify v-else-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="inspect(Boolean(key.trim()))" />

    <PageSection v-else-if="!info" :cols="4">
      <LoadingState />
    </PageSection>

    <!-- 加密备份: 先输入私钥查看内容 -->
    <CardForm v-else-if="!info.readable" @submit.prevent="inspect(true)">
      <PageSection :cols="2" :col="2" :title="t('console.backup_restore_title')" :description="t('console.backup_restore_needs_key')">
        <AlertBanner v-if="error" tone="destructive">{{ error }}</AlertBanner>
        <AlertBanner v-if="info.keyMatch === false" tone="warning">{{ t('console.backup_restore_other_key') }}</AlertBanner>
        <p v-else-if="info.keyMatch" class="text-sm text-muted-foreground">{{ t('console.backup_restore_this_key') }}</p>
        <FormField v-slot="field" :label="t('console.backup_restore_key')">
          <PasswordInput :id="field.id" v-model="key" autocomplete="off" spellcheck="false" maxlength="64" />
        </FormField>
        <FormActions>
          <Button type="submit" :disabled="busy || !key.trim()"><Eye aria-hidden="true" />{{ t('console.backup_restore_look') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>

    <PageSection v-else :cols="2" :col="2" :title="t('console.backup_restore_title')" :description="t('console.backup_restore_effect')">
      <AlertBanner v-if="error" tone="destructive">{{ error }}</AlertBanner>
      <DescriptionList :items="details" />
      <AlertBanner v-if="info.sameHost === false" tone="warning">{{ t('console.backup_restore_warn_host', { host: info.host || '?' }) }}</AlertBanner>
      <AlertBanner v-if="info.newer" tone="warning">{{ t('console.backup_restore_warn_newer', { version: info.version }) }}</AlertBanner>
      <CheckboxField v-if="info.risky" v-model="ack" :label="t('console.backup_restore_ack')" />
      <FormActions>
        <Button as-child variant="outline">
          <RouterLink to="/backup">{{ t('console.task_cancel') }}</RouterLink>
        </Button>
        <ConfirmDialog :title="t('console.backup_restore_title')" :description="t('console.backup_restore_effect')" :confirm-label="t('console.backup_restore_go')" danger @confirm="restore">
          <template #trigger>
            <Button variant="destructive" :disabled="busy || (info.risky && !ack)"><ArchiveRestore aria-hidden="true" />{{ t('console.backup_restore_go') }}</Button>
          </template>
        </ConfirmDialog>
      </FormActions>
    </PageSection>
  </CardGrid>
</template>
