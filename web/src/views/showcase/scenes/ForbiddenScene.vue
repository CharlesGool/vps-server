<script setup lang="ts">
import { Lock } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import { Button } from '@/components/ui/button'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'

// 场景: 没有权限. 说明原因和怎么办, 提供返回主页的入口; 权限必须由服务器强制, 页面只负责提示.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesForbidden')" :description="t('showcase.scenes.desc.forbidden')" :trail="trail" />
    <PageSection :cols="4">
      <EmptyState :icon="Lock" :title="t('showcase.scenes.forbiddenTitle')" :description="t('showcase.scenes.forbiddenText')">
        <template #action>
          <Button as-child variant="outline">
            <RouterLink to="/">{{ t('showcase.scenes.toHome') }}</RouterLink>
          </Button>
        </template>
      </EmptyState>
    </PageSection>

  </CardGrid>
</template>
