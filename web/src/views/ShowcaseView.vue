<script setup lang="ts">
import { Bell, ChartLine, LayoutGrid, MessagesSquare, MousePointerClick, Table, TextCursorInput, ToggleRight } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import LinkCard from '@/components/app/LinkCard.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import { SHOWCASE_PAGES } from '@/routes'

// 组件样例首页: 每个分类一张入口卡片. 只在开发和视觉测试中提供; 新增或修改共享组件时同步更新对应的子页面.
const { t } = useI18n()
const ICONS = { buttons: MousePointerClick, inputs: TextCursorInput, choices: ToggleRight, data: Table, overlays: MessagesSquare, layout: LayoutGrid, feedback: Bell, charts: ChartLine }
const titleKey = (page: string) => `page.showcase${page[0]!.toUpperCase()}${page.slice(1)}`
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcase')" :description="t('showcase.description')" />
    <LinkCard
      v-for="page in SHOWCASE_PAGES"
      :key="page"
      :to="`/showcase/${page}`"
      :title="t(titleKey(page))"
      :description="t(`showcase.desc.${page}`)"
      :icon="ICONS[page]"
    />
  </CardGrid>
</template>
