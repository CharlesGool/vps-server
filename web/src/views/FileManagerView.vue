<script setup lang="ts">
import { ArrowUp, FilePlus, FolderPlus, RefreshCw, Save, Upload } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import CheckboxField from '@/components/app/CheckboxField.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import FileUpload from '@/components/app/FileUpload.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import InputAction from '@/components/app/InputAction.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import SideDrawer from '@/components/app/SideDrawer.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import { api } from '@/lib/api'
import { fieldError } from '@/lib/errors'
import { formatBytes } from '@/lib/format'
import { useSecurePage } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// 文件管理: 列表模式, 一张整行卡片. 上面是当前路径(可直接输入后前往), 中间是目录表格(可多选, 每页 50 行),
// 下面是按钮行(上一级, 新建, 上传, 对所选项的操作). 每行的操作菜单: 打开, 编辑, 下载, 重命名, 复制, 移动, 权限, 所有者, 压缩, 解压, 删除.
// 以 root 身份读写整个文件系统, 进入前要验证管理员密码(和终端相同). 文本文件在侧边抽屉里编辑(最大 1 MiB).
interface Entry {
  name: string
  type: 'dir' | 'file' | 'link' | 'other'
  size: number | null
  modified: number
  mode: string
  octal: string
  owner: string
  group: string
  target?: string
  targetDir?: boolean
}
interface Listing { path: string; rows: Entry[]; truncated: boolean; free: number | null; users: string[]; groups: string[] }
type Op = 'mkdir' | 'touch' | 'rename' | 'copy' | 'move' | 'chmod' | 'chown' | 'compress' | 'extract'

// 长列表一页 50 行(项目决策 2026-11-20)
const PAGE = 50
const { t, te, locale } = useI18n()
const { state, guard, failure } = useSecurePage()
const listing = ref<Listing>()
const path = ref('/')
const typed = ref('/')
const page = ref(1)
const selected = ref<unknown[]>([])
const busy = ref(false)

const join = (dir: string, name: string) => (dir === '/' ? `/${name}` : `${dir}/${name}`)
const parent = (dir: string) => (dir === '/' ? '/' : dir.slice(0, dir.lastIndexOf('/')) || '/')
const errorText = (code: string) => {
  const key = `vps.fm.error.${code}`
  return te(key) ? t(key) : undefined
}
// 服务器指出被拒绝的输入项时, 提示和对话框里对应的字段用这些标签(新建和压缩时名称在 path 和 target 里)
const labels = computed(() => ({
  name: t('vps.fm.name'),
  path: t('vps.fm.name'),
  target: t('vps.fm.name'),
  destination: t('vps.fm.destination'),
  mode: t('vps.fm.octal'),
  user: t('vps.fm.user'),
  group: t('vps.fm.group'),
  format: t('vps.fm.format'),
}))
const invalid = (...names: string[]) => names.map((name) => fieldError(failure.value, name, { codes: errorText })).find(Boolean)

async function open(target: string) {
  busy.value = true
  const value = await guard(() => api<Listing>(`fm/list?path=${encodeURIComponent(target)}`), errorText)
  busy.value = false
  if (!value) return
  listing.value = value
  path.value = value.path
  typed.value = value.path
  page.value = 1
  selected.value = []
  state.value = 'ready'
}
// 当前目录写在地址的 ?path= 里, 浏览器的前进后退在目录之间切换
const route = useRoute()
const router = useRouter()
const go = (target: string) => (target === path.value && listing.value ? reload() : router.push({ path: '/filemanager', query: { path: target } }))
watch(() => route.query.path, (value) => { if (typeof value === 'string' && value !== path.value) void open(value) })
onMounted(() => open(typeof route.query.path === 'string' ? route.query.path : '/root'))
const reload = () => open(path.value)

const rows = computed(() =>
  (listing.value?.rows ?? []).slice().sort((a, b) => Number(b.type === 'dir' || !!b.targetDir) - Number(a.type === 'dir' || !!a.targetDir) || a.name.localeCompare(b.name)),
)
const pageRows = computed(() =>
  rows.value.slice((page.value - 1) * PAGE, page.value * PAGE).map((row) => ({
    ...row,
    sizeText: row.size == null ? '' : formatBytes(row.size),
    modifiedText: new Date(row.modified * 1000).toLocaleString(locale.value, { dateStyle: 'short', timeStyle: 'short' }),
    ownerText: `${row.owner}:${row.group}`,
  })),
)
watch(path, () => (selected.value = []))
const columns = computed(() => [
  { key: 'name', label: t('vps.fm.name'), mono: true },
  { key: 'sizeText', label: t('vps.fm.size'), align: 'end' as const, mono: true },
  { key: 'modifiedText', label: t('vps.fm.modified'), mono: true },
  { key: 'mode', label: t('vps.fm.mode'), mono: true },
  { key: 'ownerText', label: t('vps.fm.owner'), mono: true },
  { key: 'actions', label: t('vps.common.actions'), align: 'end' as const },
])
const isDir = (row: Entry) => row.type === 'dir' || (row.type === 'link' && !!row.targetDir)
const isArchive = (name: string) => /\.(zip|tar|tar\.gz|tgz|tar\.bz2|tar\.xz)$/i.test(name)
function menu(row: Entry) {
  const items: { key: string; label: string; danger?: boolean }[] = []
  if (isDir(row)) items.push({ key: 'open', label: t('vps.fm.open') })
  if (row.type === 'file') items.push({ key: 'edit', label: t('vps.fm.edit') })
  items.push({ key: 'download', label: t(isDir(row) ? 'vps.fm.downloadFolder' : 'vps.fm.download') })
  items.push({ key: 'rename', label: t('vps.fm.rename') }, { key: 'copy', label: t('vps.fm.copy') }, { key: 'move', label: t('vps.fm.move') })
  items.push({ key: 'chmod', label: t('vps.fm.chmod') }, { key: 'chown', label: t('vps.fm.chown') }, { key: 'compress', label: t('vps.fm.compress') })
  if (row.type === 'file' && isArchive(row.name)) items.push({ key: 'extract', label: t('vps.fm.extract') })
  items.push({ key: 'delete', label: t('vps.fm.delete'), danger: true })
  return items
}

// -- 操作 ---------------------------------------------------------------------------
const dialog = ref<{ op: Op; targets: string[] } | null>(null)
const dialogOpen = computed({ get: () => dialog.value !== null, set: (value) => { if (!value) dialog.value = null } })
const field = ref({ name: '', destination: '', mode: '0644', user: 'root', group: 'root', recursive: false, format: 'tar.gz' as 'tar.gz' | 'zip' })
const formats = [
  { value: 'tar.gz' as const, label: 'tar.gz' },
  { value: 'zip' as const, label: 'zip' },
]
const deleting = ref<string[] | null>(null)

function startOp(op: Op, targets: string[], row?: Entry) {
  const base = targets.length === 1 ? targets[0]!.split('/').pop() ?? '' : 'archive'
  field.value = {
    name: op === 'rename' ? base : op === 'compress' ? `${base}.tar.gz` : '',
    destination: op === 'extract' ? path.value : path.value,
    mode: row ? row.octal : '0644',
    user: row?.owner ?? 'root',
    group: row?.group ?? 'root',
    recursive: false,
    format: 'tar.gz',
  }
  failure.value = undefined
  dialog.value = { op, targets }
}
watch(() => field.value.format, (format) => {
  if (dialog.value?.op === 'compress') field.value.name = field.value.name.replace(/\.(tar\.gz|zip)$/, '') + (format === 'zip' ? '.zip' : '.tar.gz')
})

async function choose(row: Entry, key: string) {
  const full = join(path.value, row.name)
  if (key === 'open') return go(full)
  if (key === 'edit') return edit(full)
  if (key === 'download') return download(full)
  if (key === 'delete') {
    deleting.value = [full]
    return
  }
  startOp(key as Op, [full], row)
}
const selectedPaths = computed(() => selected.value.map((name) => join(path.value, String(name))))

async function runOp(body: Record<string, unknown>, done: string) {
  busy.value = true
  const value = await guard(() => api('fm/op', { method: 'POST', body }), errorText, labels.value)
  busy.value = false
  if (value === undefined) return false
  showToast(done, 'success')
  await reload()
  return true
}

async function submitDialog() {
  const current = dialog.value
  if (!current) return
  const f = field.value
  const one = current.targets[0] ?? ''
  const bodies: Record<Op, Record<string, unknown>> = {
    mkdir: { action: 'mkdir', path: join(path.value, f.name) },
    touch: { action: 'touch', path: join(path.value, f.name) },
    rename: { action: 'rename', path: one, name: f.name },
    copy: { action: 'copy', paths: current.targets, destination: f.destination },
    move: { action: 'move', paths: current.targets, destination: f.destination },
    chmod: { action: 'chmod', path: one, mode: f.mode, recursive: f.recursive },
    chown: { action: 'chown', path: one, user: f.user, group: f.group, recursive: f.recursive },
    compress: { action: 'compress', paths: current.targets, target: join(path.value, f.name), format: f.format },
    extract: { action: 'extract', path: one, destination: f.destination },
  }
  if (await runOp(bodies[current.op], t(`vps.fm.done.${current.op}`))) dialog.value = null
}
async function confirmDelete() {
  const targets = deleting.value
  deleting.value = null
  if (targets) await runOp({ action: 'delete', paths: targets }, t('vps.fm.done.delete', { n: targets.length }))
}

function download(full: string) {
  const link = document.createElement('a')
  link.href = `${import.meta.env.BASE_URL}api/fm/download?path=${encodeURIComponent(full)}`
  link.download = ''
  document.body.append(link)
  link.click()
  link.remove()
}

// -- 编辑 ---------------------------------------------------------------------------
const editor = ref<{ path: string; text: string; modified: number } | null>(null)
const editorOpen = computed({ get: () => editor.value !== null, set: (value) => { if (!value) editor.value = null } })
const editorText = ref('')
async function edit(full: string) {
  const value = await guard(() => api<{ path: string; text: string; modified: number }>(`fm/read?path=${encodeURIComponent(full)}`), errorText)
  if (!value) return
  editor.value = value
  editorText.value = value.text
}
async function saveEdit() {
  const current = editor.value
  if (!current) return
  busy.value = true
  const value = await guard(
    () => api<{ modified: number }>('fm/save', { method: 'POST', body: { path: current.path, text: editorText.value, modified: current.modified } }),
    errorText,
  )
  busy.value = false
  if (!value) return
  editor.value = { ...current, text: editorText.value, modified: value.modified }
  showToast(t('vps.fm.saved'), 'success')
  await reload()
}

// -- 上传 ---------------------------------------------------------------------------
const uploadOpen = ref(false)
const picked = ref<File[]>([])
const overwrite = ref(false)
const uploadPercent = ref<number>()
const uploadError = ref('')
function sendFile(file: File): Promise<string | null> {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest()
    const query = `dir=${encodeURIComponent(path.value)}&name=${encodeURIComponent(file.name)}&overwrite=${overwrite.value ? 1 : 0}`
    request.open('POST', `${import.meta.env.BASE_URL}api/fm/upload?${query}`)
    request.setRequestHeader('Content-Type', 'application/octet-stream')
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) uploadPercent.value = Math.round((event.loaded * 100) / event.total)
    }
    request.onload = () => {
      if (request.status === 200) return resolve(null)
      try {
        resolve(String(JSON.parse(request.responseText).error ?? 'failed'))
      } catch {
        resolve('failed')
      }
    }
    request.onerror = () => resolve('failed')
    request.send(file)
  })
}
async function upload() {
  uploadError.value = ''
  let sent = 0
  for (const file of picked.value) {
    uploadPercent.value = 0
    const error = await sendFile(file)
    if (error === 'security_required') {
      uploadPercent.value = undefined
      uploadOpen.value = false
      state.value = 'verify'
      return
    }
    if (error) {
      uploadError.value = `${file.name}: ${errorText(error) ?? t('vps.common.failed')}`
      break
    }
    sent += 1
  }
  uploadPercent.value = undefined
  if (sent) showToast(t('vps.fm.uploaded', { n: sent }), 'success')
  if (!uploadError.value) {
    uploadOpen.value = false
    picked.value = []
  }
  await reload()
}

const dialogTitle = computed(() => (dialog.value ? t(`vps.fm.dialog.${dialog.value.op}`) : ''))
const description = computed(() => {
  const value = listing.value
  if (!value) return undefined
  const parts = [t('vps.fm.count', { n: value.rows.length })]
  if (value.free != null) parts.push(t('vps.fm.free', { free: formatBytes(value.free) }))
  return parts.join(' · ')
})
// 确认对话框先关闭再发出 confirm: 关闭时先不清空要操作的对象, 等 confirm 处理完再清
function clearLater(clear: () => void) {
  setTimeout(clear)
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('vps.fm.title')" :description="t('vps.fm.description')" />

    <PageSection v-if="state === 'loading'" :cols="4">
      <LoadingState />
    </PageSection>
    <AdminVerify v-else-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="open(path)" />

    <CardForm v-else @submit.prevent="go(typed)">
      <PageSection :cols="4" :title="t('vps.fm.location')" :description="description">
        <FormField v-slot="fld" :label="t('vps.fm.path')">
          <InputAction :id="fld.id" v-model="typed" :action-label="t('vps.fm.go')" :action-disabled="busy || !typed.startsWith('/')" spellcheck="false" autocomplete="off" />
        </FormField>
        <AlertBanner v-if="listing?.truncated" tone="warning">{{ t('vps.fm.truncated') }}</AlertBanner>
        <DataTable long v-model:selected="selected" selectable :columns="columns" :rows="pageRows" row-key="name" :caption="t('vps.fm.location')" :empty="t('vps.fm.empty')">
          <template #cell-name="{ row }">
            <RouterLink v-if="isDir(row as unknown as Entry)" :to="{ path: '/filemanager', query: { path: join(path, String(row.name)) } }" class="font-medium text-primary underline">{{ row.name }}/</RouterLink>
            <template v-else>{{ row.name }}</template>
            <StatusBadge v-if="row.type === 'link'" tone="info">→ {{ row.target }}</StatusBadge>
          </template>
          <template #cell-actions="{ row }">
            <ActionMenu icon-only :label="t('vps.common.actionsFor', { name: String(row.name) })" :items="menu(row as unknown as Entry)" @select="choose(row as unknown as Entry, $event)" />
          </template>
        </DataTable>
        <PaginationBar v-if="rows.length > PAGE" v-model="page" :total="rows.length" :page-size="PAGE" />
        <FormActions>
          <Button variant="outline" type="button" :disabled="busy || path === '/'" @click="go(parent(path))"><ArrowUp aria-hidden="true" />{{ t('vps.fm.up') }}</Button>
          <Button variant="outline" type="button" :disabled="busy" @click="reload"><RefreshCw aria-hidden="true" />{{ t('vps.common.refresh') }}</Button>
          <Button variant="outline" type="button" :disabled="busy" @click="startOp('mkdir', [])"><FolderPlus aria-hidden="true" />{{ t('vps.fm.newFolder') }}</Button>
          <Button variant="outline" type="button" :disabled="busy" @click="startOp('touch', [])"><FilePlus aria-hidden="true" />{{ t('vps.fm.newFile') }}</Button>
          <Button v-if="selected.length" variant="outline" type="button" :disabled="busy" @click="startOp('copy', selectedPaths)">{{ t('vps.fm.copySelected', { n: selected.length }) }}</Button>
          <Button v-if="selected.length" variant="outline" type="button" :disabled="busy" @click="startOp('move', selectedPaths)">{{ t('vps.fm.moveSelected', { n: selected.length }) }}</Button>
          <Button v-if="selected.length" variant="outline" type="button" :disabled="busy" @click="startOp('compress', selectedPaths)">{{ t('vps.fm.compressSelected', { n: selected.length }) }}</Button>
          <Button v-if="selected.length" variant="destructive" type="button" :disabled="busy" @click="deleting = selectedPaths">{{ t('vps.fm.deleteSelected', { n: selected.length }) }}</Button>
          <Button type="button" :disabled="busy" @click="uploadOpen = true"><Upload aria-hidden="true" />{{ t('vps.fm.upload') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>

    <AppDialog v-model:open="dialogOpen" :title="dialogTitle" :description="dialog && dialog.targets.length > 1 ? t('vps.fm.selectedCount', { n: dialog.targets.length }) : dialog?.targets[0]">
      <template v-if="dialog">
        <FormField v-if="['mkdir', 'touch', 'rename', 'compress'].includes(dialog.op)" v-slot="fld" :label="t('vps.fm.name')" :error="invalid('name', 'path', 'target')">
          <Input :id="fld.id" v-model.trim="field.name" spellcheck="false" autocomplete="off" maxlength="255" :aria-invalid="fld.invalid" :aria-describedby="fld.describedby" />
        </FormField>
        <FormField v-if="dialog.op === 'compress'" :label="t('vps.fm.format')" group :error="invalid('format')">
          <SegmentedControl v-model="field.format" :options="formats" :label="t('vps.fm.format')" />
        </FormField>
        <FormField v-if="['copy', 'move', 'extract'].includes(dialog.op)" v-slot="fld" :label="t('vps.fm.destination')" :error="invalid('destination')">
          <Input :id="fld.id" v-model.trim="field.destination" spellcheck="false" autocomplete="off" :aria-invalid="fld.invalid" :aria-describedby="fld.describedby" />
        </FormField>
        <FormField v-if="dialog.op === 'chmod'" v-slot="fld" :label="t('vps.fm.octal')" :error="invalid('mode')">
          <Input :id="fld.id" v-model.trim="field.mode" inputmode="numeric" maxlength="4" spellcheck="false" :aria-invalid="fld.invalid" :aria-describedby="fld.describedby" />
        </FormField>
        <FormField v-if="dialog.op === 'chown'" v-slot="fld" :label="t('vps.fm.user')" :span="6" :error="invalid('user')">
          <Input :id="fld.id" v-model.trim="field.user" spellcheck="false" autocomplete="off" :aria-invalid="fld.invalid" :aria-describedby="fld.describedby" />
        </FormField>
        <FormField v-if="dialog.op === 'chown'" v-slot="fld" :label="t('vps.fm.group')" :span="6" :error="invalid('group')">
          <Input :id="fld.id" v-model.trim="field.group" spellcheck="false" autocomplete="off" :aria-invalid="fld.invalid" :aria-describedby="fld.describedby" />
        </FormField>
        <CheckboxField
          v-if="dialog.op === 'chmod' || dialog.op === 'chown'"
          v-model="field.recursive"
          :label="t('vps.fm.recursive')"
          :description="t(dialog.op === 'chmod' ? 'vps.fm.recursiveChmodHint' : 'vps.fm.recursiveChownHint')"
        />
      </template>
      <template #footer>
        <Button variant="outline" type="button" @click="dialog = null">{{ t('component.cancel') }}</Button>
        <Button type="button" :disabled="busy" @click="submitDialog">{{ dialogTitle }}</Button>
      </template>
    </AppDialog>

    <ConfirmDialog
      :open="deleting !== null"
      :title="t('vps.fm.deleteTitle', { n: deleting?.length ?? 0 })"
      :description="t('vps.fm.deleteConfirm', { names: (deleting ?? []).map((item) => item.split('/').pop()).join(', ') })"
      :confirm-label="t('vps.fm.delete')"
      danger
      @confirm="confirmDelete"
      @update:open="(open: boolean) => { if (!open) clearLater(() => (deleting = null)) }"
    />

    <AppDialog v-model:open="uploadOpen" :title="t('vps.fm.upload')" :description="t('vps.fm.uploadTo', { path })">
      <FileUpload v-model="picked" multiple :max-size="listing?.free ?? undefined" :label="t('vps.fm.upload')" />
      <CheckboxField v-model="overwrite" :label="t('vps.fm.overwrite')" />
      <ProgressBar v-if="uploadPercent !== undefined" :label="t('vps.fm.uploading')" :value="uploadPercent" />
      <AlertBanner v-if="uploadError" tone="destructive">{{ uploadError }}</AlertBanner>
      <template #footer>
        <Button variant="outline" type="button" @click="uploadOpen = false">{{ t('component.cancel') }}</Button>
        <Button type="button" :disabled="!picked.length || uploadPercent !== undefined" @click="upload"><Upload aria-hidden="true" />{{ t('vps.fm.upload') }}</Button>
      </template>
    </AppDialog>

    <SideDrawer v-model:open="editorOpen" :title="editor?.path.split('/').pop() ?? ''" :description="editor?.path">
      <FormField v-slot="fld" :label="t('vps.fm.content')">
        <Textarea :id="fld.id" v-model="editorText" size="lg" spellcheck="false" wrap="off" />
      </FormField>
      <template #footer>
        <Button variant="outline" type="button" @click="editor = null">{{ t('component.cancel') }}</Button>
        <Button type="button" :disabled="busy || editorText === editor?.text" @click="saveEdit"><Save aria-hidden="true" />{{ t('vps.common.save') }}</Button>
      </template>
    </SideDrawer>
  </CardGrid>
</template>
