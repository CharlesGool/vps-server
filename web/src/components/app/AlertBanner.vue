<script setup lang="ts">
import { CircleAlert, CircleCheck, Info, TriangleAlert } from '@lucide/vue'
import { type BlockLayout, blockAttrs } from './cardLayout'

// 页面内提示条: 不会自动消失, 放在卡片里需要用户看到的位置(表单上方, 表格上方). 会自动消失的反馈用 Toast.
// tone: info 普通, success 成功, warning 警告, destructive 错误; 警告和错误用 role="alert", 其他用 role="status". 有 title 时标题加粗.
const props = withDefaults(defineProps<{ tone?: 'info' | 'success' | 'warning' | 'destructive'; title?: string } & BlockLayout>(), { tone: 'info' })
const ICONS = { info: Info, success: CircleCheck, warning: TriangleAlert, destructive: CircleAlert }
const STYLE = {
  info: 'bg-accent text-accent-foreground',
  success: 'bg-success-surface text-success-on-surface',
  warning: 'bg-warning-surface text-warning-on-surface',
  destructive: 'bg-destructive-surface text-destructive-on-surface',
}
</script>

<template>
  <div
    data-alert
    :data-tone="tone"
    :role="tone === 'warning' || tone === 'destructive' ? 'alert' : 'status'"
    v-bind="blockAttrs(props)"
    class="flex gap-3 rounded-md border border-current/20 p-3 text-sm"
    :class="STYLE[tone]"
  >
    <span class="flex h-6 shrink-0 items-center">
      <component :is="ICONS[tone]" class="size-4" aria-hidden="true" />
    </span>
    <div class="flex min-w-0 flex-col">
      <p v-if="title" class="font-medium">{{ title }}</p>
      <p><slot /></p>
    </div>
  </div>
</template>
