<script setup lang="ts">
import { KeyRound, Plus, Save, Upload } from '@lucide/vue'
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
import CopyField from '@/components/app/CopyField.vue'
import DataTable from '@/components/app/DataTable.vue'
import FileUpload from '@/components/app/FileUpload.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import ScheduleFields, { type Spec } from '@/components/vps/ScheduleFields.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { useSecurePage } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// 配置备份: 上次恢复的结果, 定时备份设置, 备份列表(下载, 恢复, 删除, 立即备份), 备份加密和上传并排, 数据加密状态.
// 备份含控制台的全部密钥, 恢复会改写系统文件, 所以和终端一样, 进入前要验证管理员密码(useSecurePage); 验证过期时回到验证卡片.
type Run = { status: 'ok' | 'failed' | 'timeout' | 'skipped'; started: string } | null
type Item = { name: string; kind: 'manual' | 'scheduled' | 'pre-upgrade' | 'pre-restore'; sealed: boolean; keyMatch: boolean | null; created: string; size: number }
interface Backup {
  settings: { enabled: boolean; spec: Spec; keep: number; text: string }
  keepMax: number
  last: Run
  next: string | null
  backups: Item[]
  encryption: { on: boolean; fingerprint: string | null }
  data: { state: 'on' | 'off' | 'error'; encrypted: number; total: number }
  result: { ok: boolean; time: string; name: string; restored: number; error: string } | null
  timezone: string
  message: string | null
}

const { t } = useI18n()
const { state, guard } = useSecurePage()
const data = ref<Backup>()
const busy = ref(false)
const enabled = ref(false)
const spec = ref<Spec>({ mode: 'daily', time: '03:00:00' })
const keep = ref(7)
// 计划字段在第一次读取后才创建, 用读到的计划初始化
const ready = ref(false)

function apply(value: Backup, fresh = false) {
  data.value = value
  if (fresh || !ready.value) {
    enabled.value = value.settings.enabled
    spec.value = value.settings.spec
    keep.value = value.settings.keep
    ready.value = true
  }
  if (value.message) showToast(t(`console.backup_msg_${value.message}`), 'success')
}
async function load() {
  const value = await guard(() => api<Backup>('backup'))
  if (!value) return
  apply({ ...value, message: null })
  state.value = 'ready'
}
onMounted(load)
// 验证过期(security_required)或 IP 免密会话: 回到验证卡片, 和 guard 的处理相同
function expired(err: unknown) {
  if (!(err instanceof ApiError) || (err.code !== 'security_required' && err.code !== 'password_session_required')) return false
  state.value = err.code === 'security_required' ? 'verify' : 'ip'
  return true
}
const errorText = (err: unknown) => {
  const code = err instanceof ApiError ? err.code : 'failed'
  const key = `console.backup_error_${code}`
  return t(key) === key ? t('console.backup_error_failed') : t(key)
}
async function send(path: string, body: unknown, method = 'POST') {
  busy.value = true
  try {
    apply(await api<Backup>(path, { method, body }))
    return true
  } catch (err) {
    if (!isSignedOut(err) && !expired(err)) showToast(errorText(err), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

const KIND_TONES = { manual: 'neutral', scheduled: 'info', 'pre-upgrade': 'success', 'pre-restore': 'warning' } as const
const KIND_KEYS = { manual: 'manual', scheduled: 'scheduled', 'pre-upgrade': 'pre_upgrade', 'pre-restore': 'pre_restore' } as const
const size = (value: number) => {
  for (const [unit, step] of [['GiB', 1024 ** 3], ['MiB', 1024 ** 2], ['KiB', 1024]] as const) if (value >= step) return `${(value / step).toFixed(1)} ${unit}`
  return `${value} B`
}

// ---- 备份列表 ----
const page = ref(1)
const rows = computed(() => (data.value?.backups ?? []).slice((page.value - 1) * 10, page.value * 10))
const columns = computed(() => [
  { key: 'created', label: t('console.backup_restore_created'), mono: true },
  { key: 'kind', label: t('console.backup_restore_kind') },
  { key: 'size', label: t('vps.files.size'), align: 'end' as const, mono: true },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
// 每行的操作在菜单里: 下载, 恢复(打开恢复页), 删除(先确认)
const router = useRouter()
const rowActions = computed(() => [
  { key: 'download', label: t('console.backup_download') },
  { key: 'restore', label: t('console.backup_restore') },
  { key: 'delete', label: t('console.backup_delete'), danger: true },
])
// 确认对话框关闭时先于 confirm 事件改 open, 所以要删除的项单独保存
const deleting = ref<string>()
const deleteOpen = ref(false)
// 下载用带 download 属性的链接: 验证过期时服务器拒绝, 浏览器只显示下载失败, 不离开页面
function download(name: string) {
  const link = document.createElement('a')
  link.href = `/backup/download?name=${encodeURIComponent(name)}`
  link.download = ''
  document.body.append(link)
  link.click()
  link.remove()
}
function rowAction(key: string, row: Item) {
  if (key === 'download') download(row.name)
  else if (key === 'restore') void router.push({ path: '/backup/restore', query: { name: row.name } })
  else {
    deleting.value = row.name
    deleteOpen.value = true
  }
}
async function confirmDelete() {
  const name = deleting.value
  deleting.value = undefined
  if (name) await send('backup/delete', { name })
}

// ---- 备份密钥 ----
const publicKey = ref('')
const newKey = ref<{ private: string; public: string; fingerprint: string }>()
const keyOpen = computed({
  get: () => newKey.value !== undefined,
  set: (open) => {
    if (!open) newKey.value = undefined
  },
})
async function generateKey() {
  busy.value = true
  try {
    newKey.value = await api('backup/key/new', { method: 'POST', body: {} })
  } catch (err) {
    if (!isSignedOut(err) && !expired(err)) showToast(errorText(err), 'destructive')
  } finally {
    busy.value = false
  }
}
async function keyDone() {
  newKey.value = undefined
  await load()
}
async function savePublic() {
  if (await send('backup/key', { public: publicKey.value.trim() }, 'PUT')) publicKey.value = ''
}

// ---- 上传 ----
const picked = ref<File[]>([])
async function upload() {
  const file = picked.value[0]
  if (!file) return
  busy.value = true
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}api/backup/upload`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: file,
    })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new ApiError(response.status, typeof body.error === 'string' ? body.error : 'failed', body)
    picked.value = []
    apply(body as Backup)
  } catch (err) {
    if (!expired(err)) showToast(errorText(err), 'destructive')
  } finally {
    busy.value = false
  }
}

const lastText = computed(() => {
  const value = data.value
  if (!value) return ''
  const last = value.last ? `${value.last.started} · ${t(`console.task_status_${value.last.status}`)}` : t('console.backup_never')
  return `${t('console.backup_last')}: ${last}${value.next ? ` · ${t('console.backup_next')}: ${value.next}` : ''}`
})
const dataText = computed(() => {
  const value = data.value?.data
  if (!value) return ''
  if (value.state === 'on') return t('console.data_enc_on_text', { encrypted: value.encrypted, total: value.total })
  return t(value.state === 'off' ? 'console.data_enc_off_text' : 'console.data_enc_error_text')
})
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.backup')" :description="t('vps.backup.description')" />

    <AdminVerify v-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="load" />

    <PageSection v-else-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <template v-else>
      <PageSection v-if="data.result" :cols="4" :title="t('console.backup_result_title')">
        <AlertBanner :tone="data.result.ok ? 'success' : 'destructive'">
          {{ data.result.time }} ·
          {{ data.result.ok ? t('console.backup_result_ok', { files: data.result.restored, name: data.result.name }) : t('console.backup_result_failed', { name: data.result.name, error: data.result.error }) }}
        </AlertBanner>
      </PageSection>

      <!-- 定时备份 -->
      <CardForm @submit.prevent="send('backup/settings', { enabled, spec, keep }, 'PUT')">
        <PageSection :cols="4" :title="t('console.backup_schedule')" :description="t('console.backup_schedule_help')">
          <CheckboxField v-model="enabled" :label="t('console.backup_enabled')" />
          <ScheduleFields v-if="ready" v-model="spec" :timezone="data.timezone" />
          <FormField v-slot="field" :label="t('console.backup_keep')">
            <NumberField :id="field.id" v-model="keep" :min="1" :max="data.keepMax" />
          </FormField>
          <p class="text-sm text-muted-foreground">
            {{ lastText }}
          </p>
          <FormActions>
            <Button type="submit" :disabled="busy"><Save aria-hidden="true" />{{ t('console.backup_save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <!-- 备份列表 -->
      <PageSection :cols="4" :title="t('console.backup_list')" :description="t('console.backup_contents')">
        <DataTable :columns="columns" :rows="rows" row-key="name" :caption="t('console.backup_list')" :empty="t('console.backup_empty')">
          <template #cell-kind="{ row }">
            <StatusBadge :tone="KIND_TONES[row.kind]">{{ t(`console.backup_kind_${KIND_KEYS[row.kind]}`) }}</StatusBadge>
            <StatusBadge v-if="row.sealed" tone="success">{{ t('console.backup_sealed_tag') }}</StatusBadge>
            <StatusBadge v-if="row.keyMatch === false" tone="warning">{{ t('console.backup_other_key_tag') }}</StatusBadge>
          </template>
          <template #cell-size="{ row }">{{ size(row.size) }}</template>
          <template #cell-action="{ row }">
            <ActionMenu icon-only :label="`${t('component.moreActions')} ${row.created}`" :items="rowActions" @select="(key: string) => rowAction(key, row)" />
          </template>
        </DataTable>
        <PaginationBar v-if="data.backups.length > 10" v-model="page" :total="data.backups.length" />
        <FormActions>
          <Button :disabled="busy" @click="send('backup/create', {})"><Plus aria-hidden="true" />{{ t('console.backup_create') }}</Button>
        </FormActions>
      </PageSection>

      <!-- 备份加密 -->
      <CardForm @submit.prevent="savePublic">
        <PageSection :cols="2" :title="t('console.backup_enc_title')">
          <InlineGroup>
            <StatusBadge :tone="data.encryption.on ? 'success' : 'warning'">{{ t(data.encryption.on ? 'console.backup_enc_on' : 'console.backup_enc_off') }}</StatusBadge>
          </InlineGroup>
          <p class="text-sm text-muted-foreground">
            {{ data.encryption.on ? t('console.backup_enc_on_text', { fp: data.encryption.fingerprint }) : t('console.backup_enc_off_text') }}
          </p>
          <FormField v-slot="field" :label="t('console.backup_enc_own')">
            <Input :id="field.id" v-model="publicKey" maxlength="64" spellcheck="false" autocomplete="off" class="font-mono" :placeholder="t('console.backup_enc_own_placeholder')" />
          </FormField>
          <FormActions>
            <ConfirmDialog
              v-if="data.encryption.on"
              :title="t('console.backup_enc_generate')"
              :description="t('console.backup_enc_regenerate_confirm')"
              :confirm-label="t('console.backup_enc_generate')"
              @confirm="generateKey"
            >
              <template #trigger>
                <Button type="button" variant="outline" :disabled="busy"><KeyRound aria-hidden="true" />{{ t('console.backup_enc_generate') }}</Button>
              </template>
            </ConfirmDialog>
            <Button v-else type="button" variant="outline" :disabled="busy" @click="generateKey"><KeyRound aria-hidden="true" />{{ t('console.backup_enc_generate') }}</Button>
            <Button type="submit" :disabled="busy || !publicKey.trim()">{{ t('console.backup_save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <!-- 上传备份 -->
      <CardForm @submit.prevent="upload">
        <PageSection :cols="2" :title="t('console.backup_upload')" :description="t('console.backup_upload_help')">
          <FileUpload v-model="picked" accept=".gz,.sealed,application/gzip" :max-size="268435456" :label="t('console.backup_upload')" />
          <FormActions>
            <Button type="submit" :disabled="busy || !picked.length"><Upload aria-hidden="true" />{{ t('console.backup_upload_button') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <PageSection :cols="4" :title="t('console.data_enc_title')" :description="dataText">
        <InlineGroup>
          <StatusBadge :tone="data.data.state === 'on' ? 'success' : data.data.state === 'off' ? 'warning' : 'destructive'">
            {{ t(`console.data_enc_${data.data.state}`) }}
          </StatusBadge>
        </InlineGroup>
      </PageSection>
    </template>

    <ConfirmDialog
      v-model:open="deleteOpen"
      :title="t('console.backup_delete')"
      :description="t('console.backup_delete_confirm')"
      :confirm-label="t('console.backup_delete')"
      danger
      @confirm="confirmDelete"
    />

    <AppDialog v-model:open="keyOpen" :title="t('console.backup_key_page_title')">
      <AlertBanner tone="warning">{{ t('console.backup_key_page_text') }}</AlertBanner>
      <FormField v-slot="field" :label="t('console.backup_key_private')">
        <CopyField :id="field.id" :value="newKey?.private ?? ''" />
      </FormField>
      <FormField v-slot="field" :label="`${t('console.backup_key_public')} · ${newKey?.fingerprint ?? ''}`">
        <CopyField :id="field.id" :value="newKey?.public ?? ''" />
      </FormField>
      <template #footer>
        <Button @click="keyDone">{{ t('console.backup_key_done') }}</Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
