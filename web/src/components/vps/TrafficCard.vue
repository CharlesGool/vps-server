<script setup lang="ts">
import { SlidersHorizontal } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import GroupBlock from '@/components/app/GroupBlock.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageSection from '@/components/app/PageSection.vue'
import RadioField from '@/components/app/RadioField.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import ScheduleFields, { type Spec } from '@/components/vps/ScheduleFields.vue'
import { api, isSignedOut } from '@/lib/api'
import { errorText, fieldError, scheduleLabels, shownInline } from '@/lib/errors'
import { formatBytes } from '@/lib/format'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 一个计量功能(网盘, 测速, iperf3, 端口转发, FRPC, Tailscale, 域名转发)的流量卡片.
// 整行卡片: 状态, 上传/下载/上限/下次重置/有效期, 计量说明, "流量限制"对话框(上限, 限速, 超限动作, 重置周期, 有效期).
// 重置周期和定时任务用同一套计划(每周, 每月, 每年或只一次, 按服务器本地时间); 旧版本的"每隔 N 天/月/年"保留到改掉为止.
// 只由模板组件组合; 还没有计量数据时整张卡片不显示. feature 是服务器的计量键(如 'speedtest', 'frpc:<实例>').
export interface TrafficEntry {
  id: string
  state: 'blocked' | 'limited' | 'unknown' | 'normal'
  upload: number
  download: number
  uploadLimitBps: number | null
  downloadLimitBps: number | null
  capBytes: number | null
  billed: number
  multiplier: number
  capAction: 'throttle' | 'block'
  resetMode: 'none' | 'repeat' | 'once' | 'schedule'
  resetCount: number
  resetUnit: Unit
  resetSpec: Spec | null
  nextResetAt: string | null
  nextResetLocal: string | null
  expiryCount: number | null
  expiryUnit: Unit | null
  remainingSeconds: number | null
}
type Unit = 'days' | 'months' | 'years'
interface Traffic {
  entry: TrafficEntry | null
  help?: 'once' | 'twice' | 'tailscale'
  sharedWith?: string | null
  timezone?: string
}

// inline: 放在另一张卡片里(如端口转发的每条规则), 这时是卡片内带小标题的一组, 不是单独的卡片
const props = defineProps<{ feature: string; inline?: boolean }>()
const { t } = useI18n()
const data = ref<Traffic>()

onMounted(async () => {
  try {
    data.value = await api<Traffic>(`traffic?key=${encodeURIComponent(props.feature)}`)
  } catch (err) {
    if (!isSignedOut(err)) showToast(errorText(err), 'destructive')
  }
})

const entry = computed(() => data.value?.entry ?? null)
const STATES = {
  blocked: { key: 'console.node_blocked', tone: 'destructive' },
  limited: { key: 'console.node_limited', tone: 'warning' },
  unknown: { key: 'console.node_meter_unknown', tone: 'neutral' },
  normal: { key: 'console.node_normal', tone: 'success' },
} as const

const speed = (bps: number | null) => (bps == null ? t('console.node_unlimited') : `${bps / 1e6} Mbps`)
function validity(seconds: number) {
  if (seconds <= 0) return t('console.node_validity_expired')
  if (seconds < 86400) return t('console.node_remaining_hours', { count: Math.max(1, Math.ceil(seconds / 3600)) })
  return t('console.node_remaining_days', { count: Math.max(1, Math.ceil(seconds / 86400)) })
}
const items = computed(() => {
  const value = entry.value
  if (!value) return []
  const list = [
    { key: 'upload', label: t('console.node_upload'), value: `${formatBytes(value.upload)} · ${speed(value.uploadLimitBps)}` },
    { key: 'download', label: t('console.node_download'), value: `${formatBytes(value.download)} · ${speed(value.downloadLimitBps)}` },
    {
      key: 'cap',
      label: t('console.node_cap'),
      value:
        value.capBytes == null
          ? t('console.node_unlimited')
          : `${value.capBytes / 1073741824} GiB · ${t(value.multiplier === 2 ? 'console.node_billed_usage' : 'console.node_billed_usage_once', { value: formatBytes(value.billed) })}`,
    },
    { key: 'reset', label: t('console.node_next_reset'), value: value.nextResetLocal ? `${value.nextResetLocal} (${data.value?.timezone ?? ''})` : t('console.node_no_reset') },
  ]
  if (value.remainingSeconds != null) list.push({ key: 'validity', label: t('console.node_validity'), value: validity(value.remainingSeconds) })
  return list
})
const help = computed(() => ({ once: 'console.traffic_help_once', twice: 'console.traffic_help_twice', tailscale: 'console.traffic_help_tailscale' })[data.value?.help ?? 'once'])

// ---- 流量限制对话框 ----
const DEFAULT_SPEC: Spec = { mode: 'monthly', day: 1, time: '00:00:00' }
const open = ref(false)
const busy = ref(false)
const error = ref('')
// 最近一次保存失败的错误, 用来标出服务器指出的那一项
const failure = ref<unknown>()
const limitText = (code: string) => (code === 'invalid_limits' ? t('vps.traffic.invalid') : code === 'limits_failed' ? t('console.node_settings_failed') : undefined)
const invalid = (field: string) => fieldError(failure.value, field, { codes: limitText })
const labels = computed(() => ({
  capGib: t('console.node_cap_gib'),
  uploadMbps: t('console.node_upload_speed'),
  downloadMbps: t('console.node_download_speed'),
  capAction: t('console.node_cap_action'),
  resetMode: t('console.node_reset_schedule'),
  resetCount: t('console.node_reset_every'),
  resetUnit: t('console.node_reset_unit'),
  expiryMode: t('console.node_validity'),
  expiryCount: t('console.node_validity_length'),
  expiryUnit: t('console.node_validity_unit'),
  ...scheduleLabels('resetSpec'),
}))
const form = ref({
  capGib: '',
  uploadMbps: '',
  downloadMbps: '',
  capAction: 'throttle' as 'throttle' | 'block',
  resetMode: 'none' as 'none' | 'repeat' | 'schedule',
  resetCount: 1,
  resetUnit: 'months' as Unit,
  resetSpec: DEFAULT_SPEC as Spec,
  expiryMode: 'none' as 'none' | 'set',
  expiryCount: 1,
  expiryUnit: 'months' as Unit,
})
// 对话框每次打开都重新建立计划字段(ScheduleFields 只在创建时读取初始值)
const formKey = ref(0)
function edit() {
  const value = entry.value!
  formKey.value += 1
  form.value = {
    capGib: value.capBytes == null ? '' : String(value.capBytes / 1073741824),
    uploadMbps: value.uploadLimitBps == null ? '' : String(value.uploadLimitBps / 1e6),
    downloadMbps: value.downloadLimitBps == null ? '' : String(value.downloadLimitBps / 1e6),
    capAction: value.capAction,
    resetMode: value.resetMode === 'once' || value.resetMode === 'schedule' ? 'schedule' : value.resetMode,
    resetCount: value.resetCount,
    resetUnit: value.resetUnit,
    resetSpec: value.resetSpec ?? DEFAULT_SPEC,
    expiryMode: value.expiryCount ? 'set' : 'none',
    expiryCount: value.expiryCount ?? 1,
    expiryUnit: value.expiryUnit ?? 'months',
  }
  error.value = ''
  failure.value = undefined
  open.value = true
}
const capActions = computed(() => [
  { value: 'throttle' as const, label: t('console.node_cap_slow') },
  { value: 'block' as const, label: t('console.node_cap_block') },
])
// 旧版本的"每隔 N 天/月/年"只在当前就是这种设置时提供
const resetModes = computed(() => [
  { value: 'none' as const, label: t('console.node_reset_none') },
  { value: 'schedule' as const, label: t('console.node_reset_repeat') },
  ...(entry.value?.resetMode === 'repeat' ? [{ value: 'repeat' as const, label: t('vps.traffic.resetLegacy') }] : []),
])
const RESET_MODES: ('weekly' | 'monthly' | 'yearly')[] = ['weekly', 'monthly', 'yearly']
const expiryModes = computed(() => [
  { value: 'none' as const, label: t('console.node_validity_none') },
  { value: 'set' as const, label: t('console.node_validity_set') },
])
const units = computed(() => (['days', 'months', 'years'] as const).map((value) => ({ value, label: t(`console.node_${value}`) })))

async function save() {
  busy.value = true
  error.value = ''
  failure.value = undefined
  try {
    data.value = await api<Traffic>('traffic/limits', { method: 'PUT', body: { key: props.feature, ...form.value } })
    open.value = false
    showToast(t('console.node_settings_done'), 'success')
  } catch (err) {
    if (isSignedOut(err)) return
    failure.value = err
    // 服务器没说明原因时, 和以前一样是"保存失败"
    error.value = errorText(err, { codes: (code) => limitText(code) ?? t('console.node_settings_failed'), labels: labels.value })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <component
    :is="inline ? GroupBlock : PageSection"
    v-if="entry"
    v-bind="inline ? { title: t('console.node_traffic') } : { cols: 4, title: t('console.node_traffic'), description: t(help) }"
  >
    <p v-if="inline" class="text-sm text-muted-foreground">{{ t(help) }}</p>
    <div>
      <StatusBadge :tone="STATES[entry.state].tone">{{ t(STATES[entry.state].key) }}</StatusBadge>
    </div>
    <DescriptionList :items="items" />
    <p v-if="data?.sharedWith" class="text-sm text-muted-foreground">{{ t('console.traffic_frpc_shared', { names: data.sharedWith }) }}</p>
    <FormActions>
      <Button variant="outline" @click="edit"><SlidersHorizontal aria-hidden="true" />{{ t('console.traffic_limit_manage') }}</Button>
    </FormActions>
  </component>

  <AppDialog v-model:open="open" :title="t('console.traffic_limit_manage')">
    <AlertBanner v-if="error && !shownInline(failure, labels)" tone="destructive">{{ error }}</AlertBanner>
    <FormField v-slot="field" :label="t('console.node_cap_gib')" :span="4" :error="invalid('capGib')">
      <Input :id="field.id" v-model="form.capGib" inputmode="decimal" :placeholder="t('console.node_unlimited')" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
    </FormField>
    <FormField v-slot="field" :label="t('console.node_upload_speed')" :span="4" :error="invalid('uploadMbps')">
      <Input :id="field.id" v-model="form.uploadMbps" inputmode="decimal" :placeholder="t('console.node_unlimited')" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
    </FormField>
    <FormField v-slot="field" :label="t('console.node_download_speed')" :span="4" :error="invalid('downloadMbps')">
      <Input :id="field.id" v-model="form.downloadMbps" inputmode="decimal" :placeholder="t('console.node_unlimited')" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
    </FormField>
    <FormField :label="t('console.node_cap_action')" group :error="invalid('capAction')">
      <RadioField v-model="form.capAction" :options="capActions" :label="t('console.node_cap_action')" />
    </FormField>
    <FormField :label="t('console.node_reset_schedule')" group :error="invalid('resetMode')">
      <RadioField v-model="form.resetMode" :options="resetModes" :label="t('console.node_reset_schedule')" />
    </FormField>
    <ScheduleFields
      v-if="form.resetMode === 'schedule'"
      :key="formKey"
      v-model="form.resetSpec"
      :timezone="data?.timezone ?? ''"
      :modes="RESET_MODES"
      :error="(key: string) => invalid(`resetSpec.${key}`)"
    />
    <template v-if="form.resetMode === 'repeat'">
      <FormField v-slot="field" :label="t('console.node_reset_every')" :span="6" :error="invalid('resetCount')">
        <NumberField :id="field.id" v-model="form.resetCount" :min="1" :max="9999" />
      </FormField>
      <FormField :label="t('console.node_reset_unit')" group :span="6" :error="invalid('resetUnit')">
        <SegmentedControl v-model="form.resetUnit" :options="units" :label="t('console.node_reset_unit')" />
      </FormField>
    </template>
    <FormField :label="t('console.node_validity')" group :error="invalid('expiryMode')">
      <RadioField v-model="form.expiryMode" :options="expiryModes" :label="t('console.node_validity')" />
    </FormField>
    <template v-if="form.expiryMode === 'set'">
      <FormField v-slot="field" :label="t('console.node_validity_length')" :span="6" :error="invalid('expiryCount')">
        <NumberField :id="field.id" v-model="form.expiryCount" :min="1" :max="9999" />
      </FormField>
      <FormField :label="t('console.node_validity_unit')" group :span="6" :error="invalid('expiryUnit')">
        <SegmentedControl v-model="form.expiryUnit" :options="units" :label="t('console.node_validity_unit')" />
      </FormField>
    </template>
    <template #footer>
      <Button variant="outline" @click="open = false">{{ t('console.node_cancel') }}</Button>
      <Button :disabled="busy" @click="save">{{ t('console.node_save_limits') }}</Button>
    </template>
  </AppDialog>
</template>
