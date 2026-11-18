<script setup lang="ts">
import { SearchX } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import { Button } from '@/components/ui/button'

// 场景: 空页面, 如页面不存在或没有内容. 一张占满整行的卡片, 说明加一个操作.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesEmpty')" :description="t('showcase.scenes.desc.empty')" :trail="trail" />
    <PageSection :cols="4">
      <EmptyState :icon="SearchX" :title="t('showcase.scenes.notFound')" :description="t('showcase.scenes.notFoundText')">
        <template #action>
          <Button as-child variant="outline">
            <RouterLink to="/showcase">{{ t('showcase.scenes.toHome') }}</RouterLink>
          </Button>
        </template>
      </EmptyState>
    </PageSection>
  </CardGrid>
</template>
