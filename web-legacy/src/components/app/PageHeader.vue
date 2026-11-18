<script setup lang="ts">
import { ArrowLeft, Settings } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import type { RouteLocationRaw } from 'vue-router'
import { Button } from '@/components/ui/button'

// 内容区页头: 左上返回直接父级, 右上为功能自己的设置.
defineProps<{
  title: string
  description?: string
  back?: { to: RouteLocationRaw; label: string }
  settingsTo?: RouteLocationRaw
}>()

const { t } = useI18n()
</script>

<template>
  <div data-reflow class="mb-6 flex flex-col gap-3">
    <div v-if="back || settingsTo" class="flex items-center justify-between gap-3">
      <Button v-if="back" as-child variant="ghost" size="sm" class="-ml-3">
        <a :href="String(back.to)">
          <ArrowLeft aria-hidden="true" />
          {{ back.label }}
        </a>
      </Button>
      <span v-else />
      <Button v-if="settingsTo" as-child variant="outline" size="sm">
        <a :href="String(settingsTo)">
          <Settings aria-hidden="true" />
          {{ t('action.settings') }}
        </a>
      </Button>
    </div>
    <h1 class="text-2xl font-semibold">{{ title }}</h1>
    <p v-if="description" class="text-muted-foreground">{{ description }}</p>
  </div>
</template>
