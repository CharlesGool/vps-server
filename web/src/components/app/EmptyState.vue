<script setup lang="ts">
import type { Component } from 'vue'

// 列表或页面没有内容时: 图标, 标题, 说明和可选操作(action 插槽).
defineProps<{ icon: Component; title: string; description?: string }>()
</script>

<template>
  <div data-control class="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-3 py-6 text-center">
    <span class="flex size-10 items-center justify-center rounded-md bg-muted text-muted-foreground">
      <component :is="icon" class="size-5" aria-hidden="true" />
    </span>
    <p class="font-medium">{{ title }}</p>
    <p v-if="description" class="text-sm text-muted-foreground">{{ description }}</p>
    <slot name="action" />
  </div>
</template>
