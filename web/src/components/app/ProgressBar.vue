<script setup lang="ts">
import { ProgressIndicator, ProgressRoot } from 'reka-ui'

// 进度条: 标签在左, 百分比在右, 下面是 8 px 高的进度条. value 为 0 到 100.
defineProps<{ label: string; value: number }>()
</script>

<template>
  <div data-control class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-4 text-sm">
      <span class="font-medium">{{ label }}</span>
      <span class="text-muted-foreground tabular-nums">{{ value }}%</span>
    </div>
    <ProgressRoot :model-value="value" :aria-label="label" class="relative h-2 overflow-hidden rounded-full bg-secondary">
      <ProgressIndicator class="h-full rounded-full bg-primary transition-all" :style="{ width: `${value}%` }" />
    </ProgressRoot>
  </div>
</template>
