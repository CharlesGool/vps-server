<script setup lang="ts">
import { FileText, Gauge, ListChecks, Pencil, LayoutList, Loader, Lock, LogIn, Search, SearchX, Settings, SquarePen, TriangleAlert } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import LinkCard from '@/components/app/LinkCard.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import { SHOWCASE_SCENES } from '@/routes'

// 页面场景首页: 每个常见整页一张入口卡片. 场景页是静态的布局示例, 不连接后端.
const { t } = useI18n()
const ICONS = { login: LogIn, dashboard: Gauge, settings: Settings, list: LayoutList, form: SquarePen, empty: SearchX, loading: Loader, error: TriangleAlert, forbidden: Lock, detail: FileText, edit: Pencil, wizard: ListChecks, search: Search }
const titleKey = (scene: string) => `page.showcaseScenes${scene[0]!.toUpperCase()}${scene.slice(1)}`
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenes')" :description="t('showcase.desc.scenes')" />
    <LinkCard
      v-for="scene in SHOWCASE_SCENES"
      :key="scene"
      :to="`/scenes/${scene}`"
      :title="t(titleKey(scene))"
      :description="t(`showcase.scenes.desc.${scene}`)"
      :icon="ICONS[scene]"
    />
  </CardGrid>
</template>
