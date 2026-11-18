<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import SkeletonBlock from '@/components/app/SkeletonBlock.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'

// 场景: 加载中. 数据加载时用骨架屏占位, 卡片的数量, 大小和位置与加载完成后一致, 避免页面跳动; 加载超过 300 ms 才显示.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesLoading')" :description="t('showcase.scenes.desc.loading')" :trail="trail" />
    <PageSection v-for="n in 4" :key="n" :aria-busy="true">
      <SkeletonBlock :lines="1" />
      <SkeletonBlock :lines="4" />
    </PageSection>

  </CardGrid>
</template>
