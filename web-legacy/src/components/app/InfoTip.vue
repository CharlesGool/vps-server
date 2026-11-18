<script setup lang="ts">
import { Info } from '@lucide/vue'
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'

// 悬浮, 键盘焦点和触摸都能打开.
defineProps<{ text: string; label: string }>()

const id = useId()
const open = ref(false)
const root = ref<HTMLElement>()

function onOutside(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('pointerdown', onOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onOutside))
</script>

<template>
  <span
    ref="root"
    class="relative inline-flex"
    @mouseenter="open = true"
    @mouseleave="open = false"
    @keydown.escape="open = false"
  >
    <button
      type="button"
      class="flex size-6 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
      :aria-label="label"
      :aria-describedby="open ? id : undefined"
      :aria-expanded="open"
      @focus="open = true"
      @blur="open = false"
      @click="open = !open"
    >
      <Info class="size-4" aria-hidden="true" />
    </button>
    <span
      v-if="open"
      :id="id"
      role="tooltip"
      class="absolute left-1/2 top-full z-40 mt-2 w-max max-w-tip -translate-x-1/2 rounded-md border border-border bg-popover p-3 text-sm text-popover-foreground shadow-md"
    >
      {{ text }}
    </span>
  </span>
</template>
