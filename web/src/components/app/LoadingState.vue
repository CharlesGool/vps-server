<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'
import { useI18n } from 'vue-i18n'

// 加载中: 转圈加文字, 放在卡片里, 数据加载超过 300 ms 时显示. 内容有明确形状(表格, 卡片)时用 SkeletonBlock.
defineProps<{ label?: string }>()
const { t } = useI18n()
</script>

<template>
  <div role="status" class="flex items-center justify-center gap-2 py-6 text-muted-foreground">
    <LoaderCircle class="size-5 animate-spin" aria-hidden="true" />
    <span>{{ label ?? t('component.loading') }}</span>
  </div>
</template>
