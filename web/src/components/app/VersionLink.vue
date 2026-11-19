<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { APP_VERSION } from '@/app.config'

// 构建版本, 链接到应用内变更日志; 灰底小标签, 与项目名称同一行.
const { t } = useI18n()
</script>

<template>
  <RouterLink
    to="/changelog"
    class="flex min-w-6 items-center justify-center rounded-sm bg-secondary px-2 py-1 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
    :aria-label="t('nav.version', { version: APP_VERSION })"
  >
    {{ APP_VERSION }}
  </RouterLink>
</template>
