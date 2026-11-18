<script setup lang="ts">
import { computed } from 'vue'

// 迷你趋势线: 一组数值画成折线, 高 40 px, 宽度占满; 只表示趋势, 没有坐标轴, 必须配 label 说明含义(给读屏). 颜色是主题色.
const props = defineProps<{ values: number[]; label: string }>()
const WIDTH = 120
const HEIGHT = 40
const points = computed(() => {
  const min = Math.min(...props.values)
  const max = Math.max(...props.values)
  const span = max - min || 1
  return props.values.map((value, index) => `${(index / Math.max(1, props.values.length - 1)) * WIDTH},${HEIGHT - 4 - ((value - min) / span) * (HEIGHT - 8)}`).join(' ')
})
</script>

<template>
  <svg role="img" :aria-label="label" :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" preserveAspectRatio="none" class="block h-10 w-full">
    <polyline :points="points" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" class="stroke-primary" />
  </svg>
</template>
