<script setup lang="ts">
import { CloudDownload, Link, SlidersHorizontal, Trash2, Upload, X } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import CopyField from '@/components/app/CopyField.vue'
import DataTable from '@/components/app/DataTable.vue'
import FileUpload from '@/components/app/FileUpload.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import GroupBlock from '@/components/app/GroupBlock.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import SelectMenu from '@/components/app/SelectMenu.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// 迷你网盘: 容量(用量, 上限和限速的对话框), 流量, 两种添加方式并排(服务器从链接下载, 从这台设备上传), 下载任务, 文件表格.
// 每个文件的下载链接在对话框里管理(复制, 作废, 生成新链接).
type FileLink = { token: string; url: string; expires: number | null; downloads: number; max: number | null }
type FileEntry = { id: string; name: string; size: number; created: number; source: string; links: FileLink[] }
type Job = { id: string; name: string; url: string; state: 'running' | 'done' | 'failed'; bytes: number; total: number | null; error: string }
interface Files {
  used: number
  quota: number
  room: number
  diskFree: number
  rate: number
  linkMinutes: number[]
  defaultLinkMinutes: number
  files: FileEntry[]
  jobs: Job[]
  message: string | null
}

const { t } = useI18n()
const data = ref<Files>()
const busy = ref(false)

// 和服务器的 human_size 一致: 1 位小数
const size = (value: number) => {
  for (const [unit, step] of [['GiB', 1024 ** 3], ['MiB', 1024 ** 2], ['KiB', 1024]] as const) if (value >= step) return `${(value / step).toFixed(1)} ${unit}`
  return `${value} B`
}
const pad = (value: number) => String(value).padStart(2, '0')
const date = (stamp: number | null) => {
  if (!stamp) return '—'
  const d = new Date(stamp * 1000)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
const errorText = (code: string) => (code.startsWith('http_') ? t('legacy.files_error_http', { code: code.slice(5) }) : t(`legacy.files_error_${code}`))

// 有下载任务在进行时每 2 秒刷新
let timer: ReturnType<typeof setTimeout> | undefined
function apply(value: Files) {
  data.value = value
  if (value.message) showToast(t(`legacy.${value.message}`), 'success')
  clearTimeout(timer)
  if (value.jobs.some((job) => job.state === 'running')) timer = setTimeout(load, 2000)
}
async function load() {
  try {
    apply({ ...(await api<Files>('files')), message: null })
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

async function send(path: string, body: unknown, method = 'POST') {
  busy.value = true
  try {
    apply(await api<Files>(path, { method, body }))
    return true
  } catch (err) {
    if (err instanceof ApiError && err.status === 400) showToast(errorText(err.code), 'destructive')
    else if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

// ---- 容量 ----
const percent = computed(() => (data.value?.quota ? Math.min(100, Math.round((data.value.used * 100) / data.value.quota)) : 100))
const rateText = computed(() => (data.value?.rate ? `${data.value.rate / 1024 ** 2} MiB/s` : t('legacy.files_rate_none')))
const limitsOpen = ref(false)
const quotaGib = ref('')
const rateMib = ref('')
function openLimits() {
  quotaGib.value = String(data.value!.quota / 1024 ** 3)
  rateMib.value = data.value!.rate ? String(data.value!.rate / 1024 ** 2) : ''
  limitsOpen.value = true
}
async function saveLimits() {
  const quota = Number(quotaGib.value)
  const rate = rateMib.value.trim() ? Number(rateMib.value) : null
  if (await send('files/limits', { quotaGib: quota, rateMib: rate }, 'PUT')) limitsOpen.value = false
}

// ---- 添加文件 ----
// 写在模板属性里的网址会让 vue-tsc 误判后面的插槽变量, 所以放在这里
const URL_EXAMPLE = 'https://github.com/…/releases/download/…'
const fetchAddress = ref('')
async function fetchUrl() {
  if (await send('files/fetch', { url: fetchAddress.value.trim() })) fetchAddress.value = ''
}
const picked = ref<File[]>([])
const uploadPercent = ref<number>()
function upload() {
  const file = picked.value[0]
  if (!file || uploadPercent.value !== undefined) return
  // fetch 没有上传进度, 用 XMLHttpRequest; 文件作为原始请求体发送
  const request = new XMLHttpRequest()
  request.open('POST', `${import.meta.env.BASE_URL}api/files/upload?name=${encodeURIComponent(file.name)}`)
  request.setRequestHeader('Content-Type', 'application/octet-stream')
  request.upload.onprogress = (event) => {
    if (event.lengthComputable) uploadPercent.value = Math.round((event.loaded * 100) / event.total)
  }
  request.onload = () => {
    uploadPercent.value = undefined
    let body: { error?: string } & Partial<Files> = {}
    try {
      body = JSON.parse(request.responseText)
    } catch {
      // 非 JSON 回应按失败处理
    }
    if (request.status === 200 && body.files) {
      picked.value = []
      apply(body as Files)
    } else showToast(body.error ? errorText(body.error) : t('legacy.files_upload_failed'), 'destructive')
  }
  request.onerror = () => {
    uploadPercent.value = undefined
    showToast(t('legacy.files_upload_failed'), 'destructive')
  }
  uploadPercent.value = 0
  request.send(file)
}

// ---- 下载任务 ----
const jobColumns = computed(() => [
  { key: 'name', label: t('vps.files.name') },
  { key: 'state', label: t('vps.modules.status') },
  { key: 'detail', label: t('vps.files.detail') },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
const jobDetail = (job: Job) =>
  job.state === 'running'
    ? job.total
      ? `${size(job.bytes)} / ${size(job.total)} (${Math.min(100, Math.round((job.bytes * 100) / job.total))}%)`
      : size(job.bytes)
    : job.state === 'done'
      ? size(job.bytes)
      : errorText(job.error)
const JOB_STATES = {
  running: { tone: 'info', key: 'legacy.files_job_running' },
  done: { tone: 'success', key: 'legacy.files_job_done' },
  failed: { tone: 'destructive', key: 'legacy.files_job_failed' },
} as const

// ---- 文件 ----
const page = ref(1)
const fileRows = computed(() => (data.value?.files ?? []).slice((page.value - 1) * 10, page.value * 10))
watch(
  () => data.value?.files.length ?? 0,
  (count) => {
    if ((page.value - 1) * 10 >= count) page.value = Math.max(1, Math.ceil(count / 10))
  },
)
const fileColumns = computed(() => [
  { key: 'name', label: t('vps.files.name') },
  { key: 'size', label: t('vps.files.size'), align: 'end' as const, mono: true },
  { key: 'created', label: t('vps.files.created'), mono: true },
  { key: 'source', label: t('vps.files.source') },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
const sourceText = (entry: FileEntry) => (entry.source === 'upload' ? t('legacy.files_source_upload') : t('legacy.files_source_url', { url: entry.source }))

// 下载链接对话框
const linksFor = ref<string>()
const linkFile = computed(() => data.value?.files.find((entry) => entry.id === linksFor.value))
const linksOpen = computed({
  get: () => linkFile.value !== undefined,
  set: (open) => {
    if (!open) linksFor.value = undefined
  },
})
const minutes = ref('')
const maxDownloads = ref('')
function lifetime(value: number) {
  if (value === 0) return t('legacy.files_link_forever')
  if (value % 1440 === 0) return value === 1440 ? t('legacy.files_link_one_day') : t('legacy.files_link_days', { days: value / 1440 })
  if (value % 60 === 0) return value === 60 ? t('legacy.files_link_one_hour') : t('legacy.files_link_hours', { hours: value / 60 })
  return t('legacy.files_link_minutes', { minutes: value })
}
const minuteOptions = computed(() => (data.value?.linkMinutes ?? []).map((value) => ({ value: String(value), label: lifetime(value) })))
function openLinks(entry: FileEntry) {
  minutes.value = String(data.value!.defaultLinkMinutes)
  maxDownloads.value = ''
  linksFor.value = entry.id
}
async function addLink() {
  const limit = maxDownloads.value.trim()
  if (limit && !/^\d+$/.test(limit)) return showToast(t('legacy.files_error_link_invalid'), 'destructive')
  if (await send('files/link', { file: linksFor.value, minutes: Number(minutes.value), max: limit ? Number(limit) : null })) maxDownloads.value = ''
}
const linkMeta = (link: FileLink) =>
  `${link.expires ? t('legacy.files_link_until', { date: date(link.expires) }) : t('legacy.files_link_forever')} · ${
    link.max ? t('legacy.files_link_count_limit', { count: link.downloads, limit: link.max }) : t('legacy.files_link_count', { count: link.downloads })
  }`
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('legacy.files')" :description="t('vps.files.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <template v-else>
      <!-- 容量: 用量, 剩余, 上限和下载限速 -->
      <PageSection :cols="4" :title="t('legacy.files_usage')" :description="t('legacy.files_usage_detail', { used: size(data.used), quota: size(data.quota), free: size(data.diskFree) })">
        <ProgressBar :label="t('legacy.files_used')" :value="percent" />
        <p class="text-sm text-muted-foreground">
          {{ t('legacy.files_available') }} {{ size(data.room) }} · {{ t('legacy.files_rate_label') }}: {{ rateText }}
        </p>
        <FormActions>
          <Button variant="outline" @click="openLimits"><SlidersHorizontal aria-hidden="true" />{{ t('vps.files.limits') }}</Button>
        </FormActions>
      </PageSection>

      <TrafficCard feature="files" />

      <!-- 两种添加方式并排 -->
      <CardForm @submit.prevent="fetchUrl">
        <PageSection :cols="2" :title="t('legacy.files_fetch_label')" :description="t('legacy.files_fetch_help')">
          <FormField v-slot="field" :label="t('vps.files.url')">
            <Input :id="field.id" v-model="fetchAddress" type="url" maxlength="2000" :placeholder="URL_EXAMPLE" autocomplete="off" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy || !fetchAddress.trim()"><CloudDownload aria-hidden="true" />{{ t('legacy.files_fetch') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>
      <CardForm @submit.prevent="upload">
        <PageSection :cols="2" :title="t('legacy.files_upload_label')" :description="t('legacy.files_upload_help', { room: size(data?.room ?? 0) })">
          <FileUpload v-model="picked" :max-size="data?.room" :label="t('legacy.files_upload_label')" />
          <ProgressBar v-if="uploadPercent !== undefined" :label="t('legacy.files_upload')" :value="uploadPercent" />
          <FormActions>
            <Button type="submit" :disabled="!picked.length || uploadPercent !== undefined"><Upload aria-hidden="true" />{{ t('legacy.files_upload') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <PageSection v-if="data?.jobs.length" :cols="4" :title="t('legacy.files_jobs')">
        <DataTable :columns="jobColumns" :rows="data?.jobs ?? []" row-key="id" :caption="t('legacy.files_jobs')" :empty="t('legacy.files_empty')">
          <template #cell-name="{ row }">{{ row.name || row.url }}</template>
          <template #cell-state="{ row }">
            <StatusBadge :tone="JOB_STATES[row.state].tone">{{ t(JOB_STATES[row.state].key) }}</StatusBadge>
          </template>
          <template #cell-detail="{ row }">{{ jobDetail(row) }}</template>
          <template #cell-action="{ row }">
            <Button variant="outline" size="sm" :disabled="busy" @click="send('files/job', { job: row.id, action: row.state === 'running' ? 'cancel' : 'remove' })">
              <X aria-hidden="true" />{{ row.state === 'running' ? t('legacy.files_job_cancel') : t('legacy.files_job_remove') }}
            </Button>
          </template>
        </DataTable>
      </PageSection>

      <PageSection :cols="4" :title="t('legacy.files_files')" :description="t('legacy.files_link_help')">
        <DataTable :columns="fileColumns" :rows="fileRows" row-key="id" :caption="t('legacy.files_files')" :empty="t('legacy.files_empty')">
          <template #cell-size="{ row }">{{ size(row.size) }}</template>
          <template #cell-created="{ row }">{{ date(row.created) }}</template>
          <template #cell-source="{ row }">{{ sourceText(row) }}</template>
          <template #cell-action="{ row }">
            <Button variant="outline" size="sm" @click="openLinks(row)"><Link aria-hidden="true" />{{ t('vps.files.links', { count: row.links.length }) }}</Button>
            <ConfirmDialog
              :title="t('legacy.files_delete')"
              :description="t('legacy.files_delete_confirm', { name: row.name })"
              :confirm-label="t('legacy.files_delete')"
              danger
              @confirm="send('files/delete', { file: row.id })"
            >
              <template #trigger>
                <Button variant="destructive" size="sm" :disabled="busy" :aria-label="`${t('legacy.files_delete')} ${row.name}`"><Trash2 aria-hidden="true" />{{ t('legacy.files_delete') }}</Button>
              </template>
            </ConfirmDialog>
          </template>
        </DataTable>
        <PaginationBar v-if="(data?.files.length ?? 0) > 10" v-model="page" :total="data?.files.length ?? 0" />
      </PageSection>
    </template>

    <AppDialog v-model:open="limitsOpen" :title="t('vps.files.limits')" :description="t('legacy.files_quota_help')">
      <FormField v-slot="field" :label="t('legacy.files_quota_label')" :span="6">
        <Input :id="field.id" v-model="quotaGib" inputmode="decimal" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.files_rate_label')" :span="6" :help="t('legacy.files_rate_help')">
        <Input :id="field.id" v-model="rateMib" inputmode="decimal" :placeholder="t('legacy.files_rate_none')" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="limitsOpen = false">{{ t('legacy.node_cancel') }}</Button>
        <Button :disabled="busy" @click="saveLimits">{{ t('legacy.files_quota_save') }}</Button>
      </template>
    </AppDialog>

    <AppDialog v-model:open="linksOpen" :title="t('vps.files.linksTitle', { name: linkFile?.name ?? '' })" :description="t('legacy.files_link_help')">
      <AlertBanner v-if="!linkFile?.links.length" tone="info">{{ t('vps.files.noLinks') }}</AlertBanner>
      <GroupBlock v-for="(link, index) in linkFile?.links ?? []" :key="link.token" :title="t('vps.files.linkNumber', { n: index + 1 })">
        <CopyField :value="link.url" />
        <p class="text-sm text-muted-foreground">{{ linkMeta(link) }}</p>
        <FormActions>
          <Button variant="outline" size="sm" :disabled="busy" @click="send('files/revoke', { token: link.token })"><X aria-hidden="true" />{{ t('legacy.files_link_revoke') }}</Button>
        </FormActions>
      </GroupBlock>
      <FormField v-slot="field" :label="t('legacy.files_link_expiry')" :span="6">
        <SelectMenu :id="field.id" v-model="minutes" :options="minuteOptions" :label="t('legacy.files_link_expiry')" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.files_link_limit')" :span="6">
        <Input :id="field.id" v-model="maxDownloads" inputmode="numeric" :placeholder="t('legacy.files_link_limit_placeholder')" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="linksOpen = false">{{ t('vps.files.close') }}</Button>
        <Button :disabled="busy" @click="addLink"><Link aria-hidden="true" />{{ t('legacy.files_link_add') }}</Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
