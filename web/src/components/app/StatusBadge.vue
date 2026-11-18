<script setup lang="ts">
// 状态标签: 表格和列表里显示状态的小标签. tone: neutral 灰, success 绿, warning 黄, destructive 红, info 主题色. 文字**必须**说明状态, 不能只靠颜色.
withDefaults(defineProps<{ tone?: 'neutral' | 'success' | 'warning' | 'destructive' | 'info' }>(), { tone: 'neutral' })
const STYLE = {
  neutral: 'bg-muted text-muted-foreground',
  success: 'bg-success-surface text-success-on-surface',
  warning: 'bg-warning-surface text-warning-on-surface',
  destructive: 'bg-destructive-surface text-destructive-on-surface',
  info: 'bg-accent text-accent-foreground',
}
</script>

<template>
  <span data-badge class="inline-flex h-6 items-center rounded-full px-2 text-sm font-medium whitespace-nowrap" :class="STYLE[tone]">
    <slot />
  </span>
</template>
