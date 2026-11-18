<script setup lang="ts" generic="T extends string">
import { Check, ChevronDown } from '@lucide/vue'
import {
  SelectContent,
  SelectItem,
  SelectItemIndicator,
  SelectItemText,
  SelectPortal,
  SelectRoot,
  SelectTrigger,
  SelectValue,
  SelectViewport,
} from 'reka-ui'

// 6 到 10 个互斥选项时使用; 不超过 5 个用 SegmentedControl 或 RadioField, 超过 10 个用可搜索的 ComboboxField. 替代原生 <select>.
defineProps<{
  options: { value: T; label: string; disabled?: boolean }[]
  label: string
  placeholder?: string
  id?: string
  invalid?: boolean
  describedby?: string
  disabled?: boolean
}>()
const model = defineModel<T | undefined>()
</script>

<template>
  <SelectRoot v-model="model" :disabled="disabled">
    <SelectTrigger
      :id="id"
      data-control="field"
      :aria-label="label"
      :aria-invalid="invalid || undefined"
      :aria-describedby="describedby"
      class="flex h-10 w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-3 text-sm text-foreground transition-colors disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive data-placeholder:text-muted-foreground"
    >
      <SelectValue :placeholder="placeholder" class="truncate" />
      <ChevronDown class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
    </SelectTrigger>
    <SelectPortal>
      <SelectContent
        position="popper"
        :side-offset="4"
        class="z-50 max-h-(--reka-select-content-available-height) min-w-(--reka-select-trigger-width) overflow-hidden rounded-md border border-border bg-popover text-popover-foreground shadow-md"
      >
        <SelectViewport class="p-1">
          <SelectItem
            v-for="option in options"
            :key="option.value"
            :value="option.value"
            :disabled="option.disabled"
            class="relative flex h-10 cursor-pointer select-none items-center rounded-sm pr-8 pl-2 text-sm outline-none data-disabled:pointer-events-none data-disabled:opacity-50 data-highlighted:bg-accent data-highlighted:text-accent-foreground"
          >
            <SelectItemText>{{ option.label }}</SelectItemText>
            <SelectItemIndicator class="absolute right-2">
              <Check class="size-4" aria-hidden="true" />
            </SelectItemIndicator>
          </SelectItem>
        </SelectViewport>
      </SelectContent>
    </SelectPortal>
  </SelectRoot>
</template>
