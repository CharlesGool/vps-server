<script setup lang="ts">
import { TriangleAlert } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import { Button } from '@/components/ui/button'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'

// 场景: 加载失败. 一张整行卡片: 提示条说明原因, 下面是空状态样式的说明和"重试"按钮; 出错的位置只替换出错的卡片, 其他卡片照常显示.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesError')" :description="t('showcase.scenes.desc.error')" :trail="trail" />
    <PageSection :cols="4">
      <AlertBanner tone="destructive">{{ t('showcase.scenes.errorText') }}</AlertBanner>
      <EmptyState :icon="TriangleAlert" :title="t('showcase.scenes.errorTitle')" :description="t('showcase.scenes.errorText')">
        <template #action>
          <Button variant="outline">{{ t('showcase.scenes.retry') }}</Button>
        </template>
      </EmptyState>
    </PageSection>

  </CardGrid>
</template>
