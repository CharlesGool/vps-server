<script setup lang="ts">
// 日志输出: 等宽文字, 保留换行, 长行在任意位置折行. 超过 256 px 高时在框内滚动; 框可以获得焦点, 用键盘滚动.
// label 是读屏名称(通常与卡片标题相同). text 为空时显示 empty(灰色).
defineProps<{ text: string; label: string; empty?: string }>()
</script>

<template>
  <pre
    data-log-output
    role="log"
    tabindex="0"
    :aria-label="label"
    class="max-h-64 overflow-auto rounded-md border border-border bg-muted p-3 font-mono text-sm whitespace-pre-wrap wrap-anywhere"
    :class="!text && 'text-muted-foreground'"
    >{{ text || empty }}</pre
  >
</template>
