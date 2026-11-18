<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

// 时间选择: 两列可滚动的列表, 左边时(00 到 23), 右边分(00 到 59), 选中的项高亮. 只报告选择, 由 DateTimePicker 的"确定"写入.
const props = defineProps<{ hour?: number; minute?: number }>()
const emit = defineEmits<{ select: [hour: number, minute: number] }>()
const { t } = useI18n()
const hours = Array.from({ length: 24 }, (_, i) => i)
const minutes = Array.from({ length: 60 }, (_, i) => i)
const root = ref<HTMLElement>()
const pad = (value: number) => String(value).padStart(2, '0')

// 打开时把选中的项滚到中间
onMounted(async () => {
  await nextTick()
  for (const selected of root.value?.querySelectorAll('[aria-selected="true"]') ?? []) selected.scrollIntoView({ block: 'center' })
})
</script>

<template>
  <div ref="root" class="flex gap-2">
    <div class="flex flex-col items-center gap-1">
      <span class="text-sm text-muted-foreground" aria-hidden="true">{{ t('component.hour') }}</span>
      <div role="listbox" :aria-label="t('component.hour')" class="time-list flex max-h-40 sm:max-h-64 flex-col gap-1 overflow-y-auto">
        <button
          v-for="hour in hours"
          :key="hour"
          type="button"
          role="option"
          :aria-selected="hour === props.hour"
          class="flex h-8 w-12 shrink-0 items-center justify-center rounded-md text-sm tabular-nums transition-colors hover:bg-accent hover:text-accent-foreground aria-selected:bg-primary aria-selected:text-primary-foreground"
          @click="emit('select', hour, props.minute ?? 0)"
        >
          {{ pad(hour) }}
        </button>
      </div>
    </div>
    <div class="flex flex-col items-center gap-1">
      <span class="text-sm text-muted-foreground" aria-hidden="true">{{ t('component.minute') }}</span>
      <div role="listbox" :aria-label="t('component.minute')" class="time-list flex max-h-40 sm:max-h-64 flex-col gap-1 overflow-y-auto">
        <button
          v-for="minute in minutes"
          :key="minute"
          type="button"
          role="option"
          :aria-selected="minute === props.minute"
          class="flex h-8 w-12 shrink-0 items-center justify-center rounded-md text-sm tabular-nums transition-colors hover:bg-accent hover:text-accent-foreground aria-selected:bg-primary aria-selected:text-primary-foreground"
          @click="emit('select', props.hour ?? 0, minute)"
        >
          {{ pad(minute) }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 列表可以滚动, 但不显示滚动条, 两列看起来整齐 */
.time-list {
  scrollbar-width: none;
}
</style>
