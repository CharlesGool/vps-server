<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// 骨架屏: 数据加载时显示内容的大致形状, 一行一条; 加载完成后换成真实内容, 高度尽量一致避免页面跳动.
withDefaults(defineProps<{ lines?: number }>(), { lines: 3 })
const { t } = useI18n()
</script>

<template>
  <div role="status" :aria-label="t('component.loading')" class="flex flex-col gap-2">
    <span v-for="line in lines" :key="line" class="block h-4 animate-pulse rounded-sm bg-muted" :class="line === lines && lines > 1 ? 'w-3/4' : 'w-full'" aria-hidden="true" />
  </div>
</template>
