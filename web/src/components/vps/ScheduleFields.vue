<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import ComboboxField from '@/components/app/ComboboxField.vue'
import DateTimePicker from '@/components/app/DateTimePicker.vue'
import FormField from '@/components/app/FormField.vue'
import NumberField from '@/components/app/NumberField.vue'
import RadioField from '@/components/app/RadioField.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { Input } from '@/components/ui/input'

// vps-server 项目组件: 定时任务, 定时备份和流量重置共用的"什么时候"字段, 是卡片(或对话框)里的一组块.
// 先选类型: 循环执行或只执行一次. 循环的频率: 每隔一段时间, 每天, 每周, 每月, 每年, cron 表达式; 再按频率显示需要的字段.
// v-model 是服务器的计划格式(scheduler.normalize_spec): { mode, n, unit } / { mode, time } / { mode, days, time } /
// { mode, day, time } / { mode, month, day, time } / { mode, expr } / { mode: 'once', date, time }; 时间是 HH:MM:SS, 这里精确到分钟.
// timezone 是服务器的时区名称, 计划按服务器本地时间运行.
// modes 限定可选的频率(默认除每年外全部), once 为 false 时不提供"只执行一次"(如总流量重置).
export type Spec = {
  mode: 'interval' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'cron' | 'once'
  n?: number
  month?: number
  unit?: 'minutes' | 'hours' | 'days'
  time?: string
  days?: number[]
  day?: number
  date?: string
  expr?: string
}
type Recurring = Exclude<Spec['mode'], 'once'>
const props = withDefaults(defineProps<{ timezone: string; modes?: Recurring[]; once?: boolean }>(), {
  modes: () => ['interval', 'daily', 'weekly', 'monthly', 'cron'],
  once: true,
})
const spec = defineModel<Spec>({ required: true })
const { t } = useI18n()

const pad = (value: number) => String(value).padStart(2, '0')
function tomorrow() {
  const day = new Date(Date.now() + 86400000)
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}
// 各字段在切换频率时保留, 切回来还是原来的值
const initial = spec.value
const kind = ref<'recurring' | 'once'>(initial.mode === 'once' && props.once ? 'once' : 'recurring')
const mode = ref<Recurring>(initial.mode !== 'once' && props.modes.includes(initial.mode) ? initial.mode : props.modes.includes('daily') ? 'daily' : props.modes[0]!)
const n = ref(initial.n ?? 30)
const unit = ref<NonNullable<Spec['unit']>>(initial.unit ?? 'minutes')
const time = ref((initial.time ?? '03:00:00').slice(0, 5))
const days = ref((initial.days ?? [1]).map(String))
const day = ref(initial.day ?? 1)
const month = ref(String(initial.month ?? 1))
const date = ref(initial.date ?? tomorrow())
const expr = ref(initial.expr ?? '0 3 * * *')

watch([kind, mode, n, unit, time, days, day, month, date, expr], () => {
  const at = time.value ? `${time.value}:00` : ''
  if (kind.value === 'once') spec.value = { mode: 'once', date: date.value, time: at }
  else if (mode.value === 'interval') spec.value = { mode: 'interval', n: n.value, unit: unit.value }
  else if (mode.value === 'daily') spec.value = { mode: 'daily', time: at }
  else if (mode.value === 'weekly') spec.value = { mode: 'weekly', time: at, days: days.value.map(Number).sort() }
  else if (mode.value === 'monthly') spec.value = { mode: 'monthly', time: at, day: day.value }
  else if (mode.value === 'yearly') spec.value = { mode: 'yearly', time: at, month: Number(month.value), day: day.value }
  else spec.value = { mode: 'cron', expr: expr.value }
})

const kinds = computed(() => (['recurring', 'once'] as const).map((value) => ({ value, label: t(`console.task_kind_${value}`) })))
const modeOptions = computed(() => props.modes.map((value) => ({ value, label: t(`console.task_mode_${value}`) })))
const months = computed(() => Array.from({ length: 12 }, (_, index) => ({ value: String(index + 1), label: t('console.task_month_n', { n: index + 1 }) })))
const units = computed(() => (['minutes', 'hours', 'days'] as const).map((value) => ({ value, label: t(`console.task_unit_${value}`) })))
// 星期一在前, 星期日在后
const weekdays = computed(() => [1, 2, 3, 4, 5, 6, 0].map((value) => ({ value: String(value), label: t(`console.task_dayfull_${value}`) })))
const showTime = computed(() => kind.value === 'once' || ['daily', 'weekly', 'monthly', 'yearly'].includes(mode.value))
// 每天和只执行一次时时间独占一行; 每周和每月时和星期/日期并排
const timeSpan = computed<6 | 12>(() => (kind.value === 'once' || mode.value === 'daily' ? 12 : 6))
const timeHelp = computed(() => `${t('console.task_timezone')}: ${props.timezone}`)
</script>

<template>
  <FormField v-if="once" :label="t('console.task_kind')" group :span="6">
    <SegmentedControl v-model="kind" :options="kinds" :label="t('console.task_kind')" />
  </FormField>
  <FormField v-if="kind === 'once'" v-slot="field" :label="t('console.task_date')" :span="6">
    <DateTimePicker :id="field.id" v-model="date" :label="t('console.task_date')" />
  </FormField>
  <FormField v-else :label="t('console.task_mode')" group :span="once ? 6 : 12">
    <RadioField v-model="mode" :options="modeOptions" :label="t('console.task_mode')" />
  </FormField>
  <template v-if="kind === 'recurring' && mode === 'interval'">
    <FormField v-slot="field" :label="t('console.task_every')" :span="6">
      <NumberField :id="field.id" v-model="n" :min="1" :max="9999" />
    </FormField>
    <FormField :label="t('console.task_unit')" group :span="6">
      <SegmentedControl v-model="unit" :options="units" :label="t('console.task_unit')" />
    </FormField>
  </template>
  <FormField v-if="kind === 'recurring' && mode === 'weekly'" v-slot="field" :label="t('console.task_weekdays')" :span="6">
    <ComboboxField :id="field.id" v-model="days" :options="weekdays" :label="t('console.task_weekdays')" multiple />
  </FormField>
  <FormField v-if="kind === 'recurring' && mode === 'monthly'" v-slot="field" :label="t('console.task_month_day')" :help="t('console.task_month_day_help')" :span="6">
    <NumberField :id="field.id" v-model="day" :min="1" :max="31" />
  </FormField>
  <template v-if="kind === 'recurring' && mode === 'yearly'">
    <FormField v-slot="field" :label="t('console.task_month')" :span="3">
      <ComboboxField :id="field.id" v-model="month" :options="months" :label="t('console.task_month')" />
    </FormField>
    <FormField v-slot="field" :label="t('console.task_day_number')" :span="3">
      <NumberField :id="field.id" v-model="day" :min="1" :max="31" />
    </FormField>
  </template>
  <FormField v-if="showTime" v-slot="field" :label="t('console.task_time')" :help="timeHelp" :span="timeSpan">
    <DateTimePicker :id="field.id" v-model="time" mode="time" :label="t('console.task_time')" />
  </FormField>
  <FormField v-if="kind === 'recurring' && mode === 'cron'" v-slot="field" :label="t('console.task_schedule')" :help="t('console.task_schedule_help')">
    <Input :id="field.id" v-model="expr" maxlength="100" spellcheck="false" autocomplete="off" class="font-mono" />
  </FormField>
</template>
