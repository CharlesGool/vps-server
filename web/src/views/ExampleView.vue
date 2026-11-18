<script setup lang="ts">
import { AppWindow, Blocks, ScrollText, Settings } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { FEATURES, SHOWCASE } from '@/app.config'
import CardGrid from '@/components/app/CardGrid.vue'
import LinkCard from '@/components/app/LinkCard.vue'
import PageHeader from '@/components/app/PageHeader.vue'

// 示例功能页面(没有仪表板时就是主页): 四张入口卡片. 复制模板后替换为实际功能的内容.
// 组件样例和场景样例只在开发和测试构建中提供.
const { t } = useI18n()
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.example')" :description="t('example.description')" :root="!FEATURES.dashboard" />
    <LinkCard v-if="SHOWCASE" to="/showcase" :title="t('page.showcase')" :description="t('settings.showcaseDescription')" :icon="Blocks" />
    <LinkCard v-if="SHOWCASE" to="/scenes" :title="t('page.showcaseScenes')" :description="t('showcase.desc.scenes')" :icon="AppWindow" />
    <LinkCard to="/changelog" :title="t('page.changelog')" :description="t('home.changelogDescription')" :icon="ScrollText" />
    <LinkCard to="/settings" :title="t('page.settings')" :description="t('home.settingsDescription')" :icon="Settings" />
  </CardGrid>
</template>
