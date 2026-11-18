<script setup lang="ts" generic="T extends string">
import { Check, ChevronDown } from '@lucide/vue'
import {
  ComboboxAnchor,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxItemIndicator,
  ComboboxPortal,
  ComboboxRoot,
  ComboboxTrigger,
  ComboboxViewport,
} from 'reka-ui'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// 可搜索的下拉框: 选项很多(超过 10 个)时用, 输入文字筛选; multiple 时可多选, 选中的数量显示在右边, 选中项在列表里打勾. 选项 5 个以内用 SegmentedControl 或 RadioField, 6 到 10 个用 SelectMenu.
const props = defineProps<{
  options: { value: T; label: string }[]
  label: string
  placeholder?: string
  id?: string
  multiple?: boolean
  invalid?: boolean
  describedby?: string
}>()
const model = defineModel<T | T[] | undefined>()
const { t } = useI18n()
const labelOf = (value: unknown) => props.options.find((option) => option.value === value)?.label ?? ''
const count = computed(() => (Array.isArray(model.value) ? model.value.length : 0))
</script>

<template>
  <ComboboxRoot v-model="model" :multiple="multiple" :open-on-focus="true">
    <ComboboxAnchor
      data-control="field"
      class="flex h-10 w-full items-center gap-2 rounded-md border border-input bg-card pl-3 text-sm focus-within:border-ring"
      :class="invalid && 'border-destructive'"
    >
      <ComboboxInput
        :id="id"
        :aria-label="label"
        :aria-invalid="invalid || undefined"
        :aria-describedby="describedby"
        :placeholder="placeholder"
        :display-value="(value) => (multiple ? '' : labelOf(value))"
        class="h-full min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
      />
      <span v-if="multiple && count" class="shrink-0 text-muted-foreground">{{ t('component.selectedCount', { count }) }}</span>
      <ComboboxTrigger class="mr-1 flex size-8 shrink-0 items-center justify-center rounded-sm text-muted-foreground" :aria-label="label">
        <ChevronDown class="size-4" aria-hidden="true" />
      </ComboboxTrigger>
    </ComboboxAnchor>
    <ComboboxPortal>
      <ComboboxContent
        position="popper"
        :side-offset="4"
        class="z-50 max-h-(--reka-combobox-content-available-height) min-w-(--reka-combobox-trigger-width) overflow-hidden rounded-md border border-border bg-popover text-popover-foreground shadow-md"
      >
        <ComboboxViewport class="p-1">
          <ComboboxEmpty class="flex h-10 items-center px-2 text-sm text-muted-foreground">{{ t('component.noMatch') }}</ComboboxEmpty>
          <ComboboxItem
            v-for="option in options"
            :key="option.value"
            :value="option.value"
            class="relative flex h-10 cursor-pointer items-center rounded-sm pr-8 pl-2 text-sm outline-none select-none data-highlighted:bg-accent data-highlighted:text-accent-foreground"
          >
            {{ option.label }}
            <ComboboxItemIndicator class="absolute right-2">
              <Check class="size-4" aria-hidden="true" />
            </ComboboxItemIndicator>
          </ComboboxItem>
        </ComboboxViewport>
      </ComboboxContent>
    </ComboboxPortal>
  </ComboboxRoot>
</template>
