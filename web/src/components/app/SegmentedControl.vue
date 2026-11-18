<script setup lang="ts" generic="T extends string">
import { ref } from 'vue'

// 2 到 5 个很短的互斥选项; 选项带说明时用 RadioField, 6 到 10 个用 SelectMenu. 开/关两项改用 SwitchField.
// 占满所在栏, 选项均分.
const props = defineProps<{ options: { value: T; label: string }[]; label: string }>()
const model = defineModel<T>({ required: true })
const buttons = ref<HTMLButtonElement[]>([])

if (import.meta.env.DEV && props.options.length > 5) {
  console.warn('SegmentedControl: more than 5 options, use SelectMenu')
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
  <div
    role="radiogroup"
    data-control
    :aria-label="label"
    class="flex flex-wrap gap-1 rounded-md bg-muted p-1"
    @keydown="onKeydown"
  >
    <button
      v-for="option in options"
      :key="option.value"
      ref="buttons"
      type="button"
      role="radio"
      :aria-checked="option.value === model"
      :tabindex="option.value === model ? 0 : -1"
      class="h-8 rounded-sm px-1 text-sm font-medium whitespace-nowrap transition-colors"
      :class="['flex-1', option.value === model ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground']"
      @click="model = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>
