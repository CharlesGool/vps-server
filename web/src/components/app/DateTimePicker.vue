<script setup lang="ts">
import { CalendarDate, CalendarDateTime, type DateValue, getLocalTimeZone, parseDate, parseDateTime, parseTime, Time, today } from '@internationalized/date'
import { CalendarDays, ChevronLeft, ChevronRight, Clock } from '@lucide/vue'
import {
  DatePickerCalendar,
  DatePickerCell,
  DatePickerCellTrigger,
  DatePickerContent,
  DatePickerField,
  DatePickerGrid,
  DatePickerGridBody,
  DatePickerGridHead,
  DatePickerGridRow,
  DatePickerHeadCell,
  DatePickerHeader,
  DatePickerInput,
  DatePickerNext,
  DatePickerPrev,
  DatePickerRoot,
  DatePickerTrigger,
  PopoverContent,
  PopoverPortal,
  PopoverRoot,
  PopoverTrigger,
  TimeFieldInput,
  TimeFieldRoot,
} from 'reka-ui'
import { computed, ref, shallowRef, watch } from 'vue'
import { Button } from '@/components/ui/button'
import SelectMenu from './SelectMenu.vue'
import TimeColumns from './TimeColumns.vue'
import { useI18n } from 'vue-i18n'

// 日期, 时间和日期时间输入: 按当前语言显示分段输入, 24 小时制. 日期带日历弹出层, 日历顶部可以直接选月份和年份;
// 时间带时和分两列的选择弹出层; 日期时间的日历右边也有时和分两列. 时间的选择点"确定"才生效, "取消"恢复原值并关闭.
// 值为字符串: date 'YYYY-MM-DD', time 'HH:mm', datetime 'YYYY-MM-DDTHH:mm'; 未填写时为 ''.
// 替代原生 <input type="date|time|datetime-local">.
const props = withDefaults(
  defineProps<{
    label: string
    mode?: 'date' | 'time' | 'datetime'
    min?: string
    max?: string
    id?: string
    invalid?: boolean
    describedby?: string
    disabled?: boolean
  }>(),
  { mode: 'date' },
)
const model = defineModel<string>({ default: '' })
const { t, locale } = useI18n()

function toDate(value: string | undefined): DateValue | undefined {
  if (!value) return undefined
  try {
    return props.mode === 'datetime' ? parseDateTime(value) : parseDate(value.slice(0, 10))
  } catch {
    return undefined
  }
}

const dateValue = computed<DateValue | undefined>({
  get: () => toDate(model.value),
  set: (value) => {
    if (!value) model.value = ''
    else if (value instanceof CalendarDateTime) model.value = value.toString().slice(0, 16)
    else model.value = (value as CalendarDate).toString()
  },
})

const timeValue = computed<Time | undefined>({
  get: () => {
    try {
      return model.value ? parseTime(model.value) : undefined
    } catch {
      return undefined
    }
  },
  set: (value) => (model.value = value ? value.toString().slice(0, 5) : ''),
})

// 日历当前显示的月份; 月份和年份选择框改变它
const placeholder = shallowRef<DateValue>(toDate(model.value) ?? today(getLocalTimeZone()))
watch(dateValue, (value) => {
  if (value) placeholder.value = value
})
const monthOptions = computed(() => {
  const format = new Intl.DateTimeFormat(locale.value, { month: 'long' })
  return Array.from({ length: 12 }, (_, i) => ({ value: String(i + 1), label: format.format(new Date(2000, i, 1)) }))
})
// 年份范围: 有 min, max 时取它们, 否则今年前 100 年到后 20 年
const yearOptions = computed(() => {
  const now = today(getLocalTimeZone()).year
  const first = toDate(props.min)?.year ?? now - 100
  const last = toDate(props.max)?.year ?? now + 20
  return Array.from({ length: last - first + 1 }, (_, i) => String(last - i)).map((value) => ({ value, label: value }))
})
const month = computed({
  get: () => String(placeholder.value.month),
  set: (value: string | undefined) => value && (placeholder.value = placeholder.value.set({ month: Number(value) })),
})
const year = computed({
  get: () => String(placeholder.value.year),
  set: (value: string | undefined) => value && (placeholder.value = placeholder.value.set({ year: Number(value) })),
})

// 时间弹出层和日期时间日历里的时, 分: 选择先记在草稿里, 点"确定"才写入, 点"取消"恢复打开前的值并关闭
const timeOpen = ref(false)
const dateOpen = ref(false)
const draft = ref<{ hour?: number; minute?: number }>({})
let snapshot = ''
watch(timeOpen, (open) => {
  if (open) draft.value = { hour: timeValue.value?.hour, minute: timeValue.value?.minute }
})
watch(dateOpen, (open) => {
  if (!open) return
  snapshot = model.value
  const value = dateValue.value
  draft.value = value instanceof CalendarDateTime ? { hour: value.hour, minute: value.minute } : {}
})
function pickDraft(hour: number, minute: number) {
  draft.value = { hour, minute }
}
function applyTime() {
  if (draft.value.hour !== undefined) timeValue.value = new Time(draft.value.hour, draft.value.minute ?? 0)
  timeOpen.value = false
}
function applyDateTime() {
  const base = dateValue.value ?? placeholder.value
  if (draft.value.hour !== undefined) dateValue.value = new CalendarDateTime(base.year, base.month, base.day, draft.value.hour, draft.value.minute ?? 0)
  dateOpen.value = false
}
function cancelDateTime() {
  model.value = snapshot
  dateOpen.value = false
}

// 可编辑的分段(年, 月, 日, 时, 分)至少 24 px 见方, 满足触控目标; 分隔符不加宽
const segmentClass =
  'whitespace-pre rounded-sm tabular-nums outline-none focus:bg-accent focus:text-accent-foreground data-placeholder:text-muted-foreground'
const segmentSize = (part: string) => (part === 'literal' ? '' : 'inline-flex h-6 min-w-6 items-center justify-center')
const fieldClass =
  'flex h-10 w-full items-center gap-2 rounded-md border border-input bg-card px-3 text-sm text-foreground transition-colors focus-within:border-ring data-disabled:opacity-50 aria-invalid:border-destructive data-invalid:border-destructive'
</script>

<template>
  <TimeFieldRoot
    v-if="mode === 'time'"
    :id="id"
    v-slot="{ segments }"
    v-model="timeValue"
    :locale="locale"
    :hour-cycle="24"
    granularity="minute"
    :disabled="disabled"
    :min-value="min ? parseTime(min) : undefined"
    :max-value="max ? parseTime(max) : undefined"
    data-control="field"
    :aria-label="label"
    :aria-invalid="invalid || undefined"
    :aria-describedby="describedby"
    :class="fieldClass"
  >
    <span class="flex flex-1 items-center">
      <TimeFieldInput v-for="item in segments" :key="item.part" :part="item.part" :class="[segmentClass, segmentSize(item.part)]">
        {{ item.value }}
      </TimeFieldInput>
    </span>
    <PopoverRoot v-model:open="timeOpen">
      <PopoverTrigger
        class="-mr-2 flex size-7 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        :aria-label="t('component.chooseTime')"
        :disabled="disabled"
      >
        <Clock class="size-4" aria-hidden="true" />
      </PopoverTrigger>
      <PopoverPortal>
        <PopoverContent
          :side-offset="4"
          align="end"
          role="dialog"
          :aria-label="label"
          class="z-50 rounded-md border border-border bg-popover p-3 text-popover-foreground shadow-md"
        >
          <TimeColumns :hour="draft.hour" :minute="draft.minute" @select="pickDraft" />
          <div class="mt-3 flex justify-end gap-2">
            <Button size="sm" variant="outline" @click="timeOpen = false">{{ t('component.cancel') }}</Button>
            <Button size="sm" @click="applyTime">{{ t('component.apply') }}</Button>
          </div>
        </PopoverContent>
      </PopoverPortal>
    </PopoverRoot>
  </TimeFieldRoot>

  <DatePickerRoot
    v-else
    :id="id"
    v-model="dateValue"
    v-model:placeholder="placeholder"
    v-model:open="dateOpen"
    :locale="locale"
    :hour-cycle="24"
    :granularity="mode === 'datetime' ? 'minute' : 'day'"
    :close-on-select="mode === 'date'"
    :min-value="toDate(min)"
    :max-value="toDate(max)"
    :disabled="disabled"
  >
    <DatePickerField
      v-slot="{ segments }"
      data-control="field"
      :aria-label="label"
      :aria-invalid="invalid || undefined"
      :aria-describedby="describedby"
      :class="fieldClass"
    >
      <span class="flex flex-1 flex-wrap items-center">
        <DatePickerInput v-for="item in segments" :key="item.part" :part="item.part" :class="[segmentClass, segmentSize(item.part)]">
          {{ item.value }}
        </DatePickerInput>
      </span>
      <DatePickerTrigger
        class="-mr-2 flex size-7 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        :aria-label="t('component.openCalendar')"
      >
        <CalendarDays class="size-4" aria-hidden="true" />
      </DatePickerTrigger>
    </DatePickerField>

    <DatePickerContent
      :side-offset="4"
      align="start"
      class="z-50 rounded-md border border-border bg-popover p-3 text-popover-foreground shadow-md"
    >
      <!-- 窄屏(手机)上日历和时分列放不下一行, 时分列移到日历下面 -->
      <div class="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
        <DatePickerCalendar v-slot="{ weekDays, grid }" :calendar-label="label">
          <DatePickerHeader class="mb-2 flex items-center justify-between gap-2">
            <DatePickerPrev
              class="flex size-8 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground"
              :aria-label="t('component.previousMonth')"
            >
              <ChevronLeft class="size-4" aria-hidden="true" />
            </DatePickerPrev>
            <!-- 月份和年份可以直接选 -->
            <div class="flex flex-1 gap-2">
              <SelectMenu v-model="month" :options="monthOptions" :label="t('component.month')" />
              <SelectMenu v-model="year" :options="yearOptions" :label="t('component.year')" />
            </div>
            <DatePickerNext
              class="flex size-8 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground"
              :aria-label="t('component.nextMonth')"
            >
              <ChevronRight class="size-4" aria-hidden="true" />
            </DatePickerNext>
          </DatePickerHeader>
          <DatePickerGrid v-for="month in grid" :key="month.value.toString()" class="border-collapse">
            <DatePickerGridHead>
              <DatePickerGridRow class="flex">
                <DatePickerHeadCell v-for="day in weekDays" :key="day" class="w-9 text-sm font-normal text-muted-foreground">
                  {{ day }}
                </DatePickerHeadCell>
              </DatePickerGridRow>
            </DatePickerGridHead>
            <DatePickerGridBody>
              <DatePickerGridRow v-for="(week, index) in month.rows" :key="index" class="mt-1 flex">
                <DatePickerCell v-for="day in week" :key="day.toString()" :date="day" class="p-0">
                  <DatePickerCellTrigger
                    :day="day"
                    :month="month.value"
                    class="flex size-9 items-center justify-center rounded-md text-sm tabular-nums outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring data-disabled:pointer-events-none data-disabled:opacity-50 data-outside-view:text-muted-foreground data-today:font-semibold data-today:text-primary data-unavailable:line-through data-selected:bg-primary data-selected:text-primary-foreground"
                  />
                </DatePickerCell>
              </DatePickerGridRow>
            </DatePickerGridBody>
          </DatePickerGrid>
        </DatePickerCalendar>
        <TimeColumns v-if="mode === 'datetime'" :hour="draft.hour" :minute="draft.minute" @select="pickDraft" />
      </div>
      <div v-if="mode === 'datetime'" class="mt-3 flex justify-end gap-2">
        <Button size="sm" variant="outline" @click="cancelDateTime">{{ t('component.cancel') }}</Button>
        <Button size="sm" @click="applyDateTime">{{ t('component.apply') }}</Button>
      </div>
    </DatePickerContent>
  </DatePickerRoot>
</template>
