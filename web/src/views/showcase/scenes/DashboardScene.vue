<script setup lang="ts">
import { Blocks, Gauge, LayoutList, Settings, Shapes } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import LinkCard from '@/components/app/LinkCard.vue'
import StatCard from '@/components/app/StatCard.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import TrendChart from '@/components/app/TrendChart.vue'

// 场景: 仪表板. 第一行 4 张数据卡, 然后是整行的趋势图, 最后每个功能一张入口卡片, 可以用 cols, rows 让重要的功能占更多格子; 这里的入口都指向样例首页.
const { t, locale } = useI18n()
const days = computed(() => Array.from({ length: 7 }, (_, index) => new Intl.DateTimeFormat(locale.value, { weekday: 'short' }).format(new Date(2026, 10, 9 + index))))
const traffic = computed(() => [{ name: t('showcase.scenes.statRequests'), values: [1420, 1630, 1580, 1810, 1760, 1950, 2240] }])
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const features = [Shapes, Blocks, LayoutList, Settings, Gauge]
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesDashboard')" :description="t('dashboard.description')" :trail="trail" />
    <!-- 数据卡: 一行 4 张指标, 然后是功能入口 -->
    <StatCard :label="t('showcase.scenes.statRequests')" value="12,480" :delta="8" :delta-label="t('showcase.scenes.vsLastWeek')" :trend="[4, 6, 5, 8, 7, 9, 12]" />
    <StatCard :label="t('showcase.scenes.statUsers')" value="1,204" :delta="3" :delta-label="t('showcase.scenes.vsLastWeek')" :trend="[5, 5, 6, 6, 7, 7, 8]" />
    <StatCard :label="t('showcase.scenes.statErrors')" value="0.8%" :delta="-12" good="down" :delta-label="t('showcase.scenes.vsLastWeek')" :trend="[9, 8, 8, 6, 5, 5, 3]" />
    <StatCard :label="t('showcase.scenes.statLatency')" value="238 ms" :delta="6" good="down" :delta-label="t('showcase.scenes.vsLastWeek')" :trend="[3, 4, 4, 5, 5, 6, 7]" />
    <!-- 趋势图占整行, 放在指标下面 -->
    <PageSection :cols="4" :title="t('showcase.scenes.traffic')">
      <TrendChart :label="t('showcase.scenes.traffic')" :labels="days" :series="traffic" />
    </PageSection>
    <LinkCard
      v-for="(icon, index) in features"
      :key="index"
      to="/showcase"
      :cols="index === 0 ? 2 : 1"
      :title="`${t('showcase.scenes.feature')} ${index + 1}`"
      :description="t('showcase.scenes.desc.dashboard')"
      :icon="icon"
    />
  </CardGrid>
</template>
