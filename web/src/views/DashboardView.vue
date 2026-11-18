<script setup lang="ts">
import { AppWindow, Blocks, Shapes } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import LinkCard from '@/components/app/LinkCard.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import { SHOWCASE } from '@/app.config'
import { FEATURE_LIST, type Feature } from '@/features'

// 仪表板: 每个功能一张入口卡片. 功能的访问权限由服务器强制; 不可访问的功能不要放入 FEATURE_LIST.
const { t } = useI18n()
const ICONS: Record<Feature['icon'], typeof Shapes> = { example: Shapes }
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.dashboard')" :description="t('dashboard.description')" root />
    <LinkCard
      v-for="feature in FEATURE_LIST"
      :key="feature.name"
      :to="feature.path"
      :title="t(feature.titleKey)"
      :description="t(feature.descriptionKey)"
      :icon="ICONS[feature.icon]"
    />
    <!-- 组件样例入口只在开发和测试构建中提供 -->
    <LinkCard v-if="SHOWCASE" to="/showcase" :title="t('page.showcase')" :description="t('settings.showcaseDescription')" :icon="Blocks" />
    <LinkCard v-if="SHOWCASE" to="/scenes" :title="t('page.showcaseScenes')" :description="t('showcase.desc.scenes')" :icon="AppWindow" />
  </CardGrid>
</template>
