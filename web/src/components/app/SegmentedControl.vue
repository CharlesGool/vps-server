<script setup lang="ts" generic="T extends string">
import { ref } from 'vue'

// 不超过 5 个互斥选项; 超过时改用 ThemeSelect 这类列表框组件.
const props = defineProps<{ options: { value: T; label: string }[]; label: string }>()
const model = defineModel<T>({ required: true })
const buttons = ref<HTMLButtonElement[]>([])

if (import.meta.env.DEV && props.options.length > 5) {
  console.warn('SegmentedControl: more than 5 options, use a listbox component')
}

function onKeydown(event: KeyboardEvent) {
  const current = props.options.findIndex((option) => option.value === model.value)
  const last = props.options.length - 1
  let next = current
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = current === last ? 0 : current + 1
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = current === 0 ? last : current - 1
  else return
  event.preventDefault()
  model.value = props.options[next]!.value
  buttons.value[next]?.focus()
}
</script>

<template>
  <div role="radiogroup" :aria-label="label" class="inline-flex flex-wrap gap-1 rounded-md bg-muted p-1" @keydown="onKeydown">
    <button data-ui-control
      v-for="option in options"
      :key="option.value"
      ref="buttons"
      type="button"
      role="radio"
      :aria-checked="option.value === model"
      :tabindex="option.value === model ? 0 : -1"
      class="h-8 rounded-sm px-3 text-sm font-medium transition-colors"
      :class="option.value === model ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
      @click="model = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>
