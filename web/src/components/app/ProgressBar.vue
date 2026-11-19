<script setup lang="ts">
import { ProgressIndicator, ProgressRoot } from 'reka-ui'

// 进度条: 标签在左, 百分比在右, 下面是 8 px 高的进度条. value 为 0 到 100.
// variant="inline": 放进表格单元格等一行的位置, 只显示一条 96 px 宽的进度条和右边的数值; label 只给读屏.
// text 替换右边显示的数值(如保留一位小数的百分比).
withDefaults(defineProps<{ label: string; value: number; variant?: 'default' | 'inline'; text?: string }>(), { variant: 'default', text: undefined })
</script>

<template>
  <div v-if="variant === 'inline'" data-progress-inline class="inline-flex items-center justify-end gap-3">
    <ProgressRoot :model-value="value" :aria-label="label" class="relative h-2 w-24 shrink-0 overflow-hidden rounded-full bg-secondary">
      <ProgressIndicator class="h-full rounded-full bg-primary transition-all" :style="{ width: `${value}%` }" />
    </ProgressRoot>
    <span class="min-w-16 text-right text-sm tabular-nums">{{ text ?? `${value}%` }}</span>
  </div>
  <div v-else data-control class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-4 text-sm">
      <span class="font-medium">{{ label }}</span>
      <span class="text-muted-foreground tabular-nums">{{ text ?? `${value}%` }}</span>
    </div>
    <ProgressRoot :model-value="value" :aria-label="label" class="relative h-2 overflow-hidden rounded-full bg-secondary">
      <ProgressIndicator class="h-full rounded-full bg-primary transition-all" :style="{ width: `${value}%` }" />
    </ProgressRoot>
  </div>
</template>
