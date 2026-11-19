<script setup lang="ts">
import { Check } from '@lucide/vue'

// 步骤条: 多步表单(向导)顶部显示进度: 已完成的步骤打勾, 当前步骤高亮, 后面的步骤灰色; 每步有编号和名称. 窄屏时步骤名称换行.
// current 从 0 开始; 只显示进度, 不可点击跳转(返回上一步用"上一步"按钮, 避免跳过校验).
defineProps<{ steps: string[]; current: number; label: string }>()
</script>

<template>
  <ol data-control :aria-label="label" class="flex flex-wrap items-center gap-x-4 gap-y-2">
    <li v-for="(step, index) in steps" :key="step" :aria-current="index === current ? 'step' : undefined" class="flex items-center gap-2 text-sm">
      <span
        class="flex size-6 shrink-0 items-center justify-center rounded-full border text-sm font-medium tabular-nums"
        :class="index < current ? 'border-primary bg-primary text-primary-foreground' : index === current ? 'border-primary text-primary' : 'border-input text-muted-foreground'"
      >
        <Check v-if="index < current" class="size-4" aria-hidden="true" />
        <template v-else>{{ index + 1 }}</template>
      </span>
      <span :class="index === current ? 'font-medium' : 'text-muted-foreground'">{{ step }}</span>
      <span v-if="index < steps.length - 1" class="h-px w-6 bg-border" aria-hidden="true" />
    </li>
  </ol>
</template>
