<script setup lang="ts">
import { History, Pencil, Play, Save, Trash2 } from '@lucide/vue'
import { computed, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import CheckboxField from '@/components/app/CheckboxField.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import GroupBlock from '@/components/app/GroupBlock.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import ScheduleFields, { type Spec } from '@/components/vps/ScheduleFields.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { errorText, fieldError, scheduleLabels, shownInline } from '@/lib/errors'
import { useSecurePage } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// 定时任务: 内置的配置备份一张卡片, 每个任务一张整行卡片(计划, 下次和上次运行, 命令, 启停开关, 立即运行, 编辑, 删除, 运行记录).
// 添加和编辑在页面最后的表单卡片里; 运行记录在对话框里.
// 任务以 root 运行命令, 所以和终端一样, 进入前要验证管理员密码(useSecurePage); 验证过期时回到验证卡片, 表单内容保留.
type Run = { status: 'ok' | 'failed' | 'timeout' | 'skipped'; started: string; exit: number | null; trigger: 'schedule' | 'manual'; output: string }
type Task = {
  id: string
  name: string
  command: string
  timeout: number
  notify: boolean
  enabled: boolean
  spec: Spec | null
  text: string
  next: string | null
  done: 'ran' | 'missed' | null
  last: Run | null
  runs: Run[]
}
interface Tasks {
  backup: { enabled: boolean; text: string; next: string | null; last: Run | null; runs: Run[] }
  tasks: Task[]
  limits: { nameMax: number; commandMax: number; timeoutMin: number; timeoutMax: number; timeoutDefault: number }
  timezone: string
  message: string | null
}

const { t, te } = useI18n()
const { state, guard } = useSecurePage()
const data = ref<Tasks>()
const busy = ref(false)
const TONES = { ok: 'success', failed: 'destructive', timeout: 'warning', skipped: 'neutral' } as const

function apply(value: Tasks) {
  data.value = value
  if (value.message) showToast(t(`console.task_msg_${value.message}`), 'success')
}
async function load() {
  const value = await guard(() => api<Tasks>('tasks'))
  if (!value) return
  const first = !data.value
  apply({ ...value, message: null })
  if (first && !form.value.id) form.value.timeout = value.limits.timeoutDefault
  state.value = 'ready'
}
onMounted(load)
// 验证过期(security_required)或 IP 免密会话: 回到验证卡片, 和 guard 的处理相同
function expired(err: unknown) {
  if (!(err instanceof ApiError) || (err.code !== 'security_required' && err.code !== 'password_session_required')) return false
  state.value = err.code === 'security_required' ? 'verify' : 'ip'
  return true
}
const taskText = (code: string) => (te(`console.task_error_${code}`) ? t(`console.task_error_${code}`) : t('console.task_error_invalid'))
// 服务器指出被拒绝的输入项时, 提示和对应的字段用这些标签
const labels = computed(() => ({
  name: t('console.task_name'),
  command: t('console.task_command'),
  timeout: t('console.task_timeout'),
  ...scheduleLabels('spec'),
}))
// 最近一次失败的请求(成功或换一个任务编辑时清空), 用来标出表单里对应的字段
const failure = ref<unknown>()
const invalid = (field: string) => fieldError(failure.value, field, { codes: taskText })
// 返回 '' 表示成功, 错误文字, 或 undefined(已转到登录页或验证卡片)
async function send(path: string, body: unknown, method = 'POST') {
  busy.value = true
  failure.value = undefined
  try {
    apply(await api<Tasks>(path, { method, body }))
    return ''
  } catch (err) {
    if (isSignedOut(err) || expired(err)) return undefined
    failure.value = err
    return errorText(err, { codes: taskText, labels: labels.value })
  } finally {
    busy.value = false
  }
}
async function act(path: string, body: unknown) {
  const error = await send(path, body)
  if (error) showToast(error, 'destructive')
}

const facts = (item: { text: string; next: string | null; last: Run | null }) => [
  { key: 'when', label: t('console.task_mode'), value: item.text || '—' },
  { key: 'next', label: t('console.task_next'), value: item.next ?? '—' },
  { key: 'last', label: t('console.task_last'), value: item.last ? item.last.started : t('console.task_never') },
]

// ---- 运行记录 ----
const historyOf = ref<{ title: string; runs: Run[] }>()
const historyOpen = computed({
  get: () => historyOf.value !== undefined,
  set: (open) => {
    if (!open) historyOf.value = undefined
  },
})

// ---- 添加和编辑: 页面底部的表单 ----
const formError = ref('')
const blank = () => ({ id: null as string | null, name: '', command: '', timeout: data.value?.limits.timeoutDefault ?? 3600, notify: true, enabled: true })
const form = ref(blank())
const spec = ref<Spec>({ mode: 'daily', time: '03:00:00' })
// 换一个任务编辑时重新创建计划字段, 让它们按这个任务初始化
const formKey = ref(0)
function reset() {
  form.value = blank()
  spec.value = { mode: 'daily', time: '03:00:00' }
  formError.value = ''
  failure.value = undefined
  formKey.value += 1
}
function openForm(task: Task) {
  form.value = { id: task.id, name: task.name, command: task.command, timeout: task.timeout, notify: task.notify, enabled: task.enabled }
  spec.value = task.spec ?? { mode: 'daily', time: '03:00:00' }
  formError.value = ''
  failure.value = undefined
  formKey.value += 1
  void nextTick(() => document.getElementById('task-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}
async function save() {
  const error = await send('tasks/save', { ...form.value, spec: spec.value }, 'PUT')
  formError.value = error ?? ''
  if (error === '') reset()
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.tasks')" :description="t('vps.tasks.description')" />

    <AdminVerify v-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="load" />

    <PageSection v-else-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <template v-else>
      <!-- 内置: 配置备份, 设置在备份页 -->
      <PageSection :cols="4" :title="t('console.task_builtin_backup')">
        <InlineGroup>
          <StatusBadge tone="info">{{ t('console.task_builtin') }}</StatusBadge>
          <StatusBadge v-if="data.backup.last" :tone="TONES[data.backup.last.status]">{{ t(`console.task_status_${data.backup.last.status}`) }}</StatusBadge>
          <StatusBadge v-if="!data.backup.enabled">{{ t('console.task_disabled') }}</StatusBadge>
        </InlineGroup>
        <DescriptionList :items="facts({ ...data.backup, text: data.backup.enabled ? data.backup.text : '' })" />
        <FormActions>
          <Button v-if="data.backup.runs.length" variant="outline" @click="historyOf = { title: t('console.task_builtin_backup'), runs: data.backup.runs }">
            <History aria-hidden="true" />{{ t('console.task_history') }} ({{ data.backup.runs.length }})
          </Button>
          <Button as-child variant="outline">
            <RouterLink to="/backup">{{ t('console.task_open') }}</RouterLink>
          </Button>
        </FormActions>
      </PageSection>

      <PageSection v-for="task in data.tasks" :key="task.id" :cols="4" :title="task.name">
        <InlineGroup>
          <StatusBadge v-if="task.last" :tone="TONES[task.last.status]">{{ t(`console.task_status_${task.last.status}`) }}</StatusBadge>
          <StatusBadge v-else>{{ t('console.task_never') }}</StatusBadge>
          <StatusBadge v-if="task.done === 'ran' || task.done === 'missed'" :tone="task.done === 'ran' ? 'success' : 'warning'">{{ t(`console.task_done_${task.done}`) }}</StatusBadge>
        </InlineGroup>
        <SwitchField
          :model-value="task.enabled"
          :label="t('vps.tasks.enabledName', { name: task.name })"
          :disabled="busy"
          @update:model-value="(value: boolean) => act('tasks/toggle', { id: task.id, enabled: value })"
        />
        <DescriptionList :items="facts(task)" />
        <LogOutput :text="task.command" :label="`${t('console.task_command')} ${task.name}`" />
        <FormActions>
          <Button v-if="task.runs.length" variant="outline" @click="historyOf = { title: task.name, runs: task.runs }">
            <History aria-hidden="true" />{{ t('console.task_history') }} ({{ task.runs.length }})
          </Button>
          <ConfirmDialog
            :title="t('console.task_delete')"
            :description="t('console.task_delete_confirm', { name: task.name })"
            :confirm-label="t('console.task_delete')"
            danger
            @confirm="act('tasks/delete', { id: task.id })"
          >
            <template #trigger>
              <Button variant="destructive" :disabled="busy" :aria-label="`${t('console.task_delete')} ${task.name}`"><Trash2 aria-hidden="true" />{{ t('console.task_delete') }}</Button>
            </template>
          </ConfirmDialog>
          <Button variant="outline" :disabled="busy" :aria-label="`${t('console.task_edit')} ${task.name}`" @click="openForm(task)"><Pencil aria-hidden="true" />{{ t('console.task_edit') }}</Button>
          <Button variant="outline" :disabled="busy" :aria-label="`${t('console.task_run')} ${task.name}`" @click="act('tasks/run', { id: task.id })"><Play aria-hidden="true" />{{ t('console.task_run') }}</Button>
        </FormActions>
      </PageSection>
      <!-- 添加或编辑任务: 页面最后一张表单卡片; 点任务的"编辑"时载入这里 -->
      <CardForm id="task-form" @submit.prevent="save">
        <PageSection :cols="4" :title="form.id ? t('console.task_edit_heading') : t('console.task_add')" :description="t('console.task_run_as_root')">
          <EmptyState v-if="!data.tasks.length && !form.id" :icon="Play" :title="t('vps.tasks.empty')" />
          <AlertBanner v-if="formError && !shownInline(failure, labels)" tone="destructive">{{ formError }}</AlertBanner>
          <FormField v-slot="field" :label="t('console.task_name')" :error="invalid('name')">
            <Input :id="field.id" v-model="form.name" :maxlength="data.limits.nameMax" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
          </FormField>
          <ScheduleFields :key="formKey" v-model="spec" :timezone="data.timezone" :error="(key: string) => invalid(`spec.${key}`)" />
          <FormField v-slot="field" :label="t('console.task_command')" :error="invalid('command')">
            <Textarea :id="field.id" v-model="form.command" :maxlength="data.limits.commandMax" spellcheck="false" class="font-mono" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
          </FormField>
          <FormField v-slot="field" :label="t('console.task_timeout')" :error="invalid('timeout')">
            <NumberField :id="field.id" v-model="form.timeout" :min="data.limits.timeoutMin" :max="data.limits.timeoutMax" />
          </FormField>
          <CheckboxField v-model="form.notify" :label="t('console.task_notify')" :span="6" />
          <CheckboxField v-model="form.enabled" :label="t('console.task_enabled')" :span="6" />
          <FormActions>
            <Button v-if="form.id" type="button" variant="outline" @click="reset">{{ t('console.task_cancel') }}</Button>
            <Button type="submit" :disabled="busy || !form.name.trim() || !form.command.trim()"><Save aria-hidden="true" />{{ t('console.task_save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>
    </template>


    <AppDialog v-model:open="historyOpen" :title="`${t('console.task_history')} · ${historyOf?.title ?? ''}`">
      <GroupBlock v-for="(run, index) in historyOf?.runs ?? []" :key="index" :title="run.started">
        <InlineGroup>
          <StatusBadge :tone="TONES[run.status]">{{ t(`console.task_status_${run.status}`) }}</StatusBadge>
          <StatusBadge>{{ t(`console.task_trigger_${run.trigger}`) }}</StatusBadge>
          <StatusBadge v-if="run.exit !== null">{{ t('console.task_exit') }} {{ run.exit }}</StatusBadge>
        </InlineGroup>
        <LogOutput v-if="run.output" :text="run.output" :label="`${t('console.task_history')} ${run.started}`" />
      </GroupBlock>
    </AppDialog>
  </CardGrid>
</template>
