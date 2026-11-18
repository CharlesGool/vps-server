<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import TrendChart from '@/components/app/TrendChart.vue'

// 组件样例: 图表. 看趋势用折线图(时间在横轴), 比较各项用柱状图; 一张卡片放一张图, 卡片标题就是图表名称.
// 时间序列一般占整行; 两张比较图并排各占 2 列.
const { t, locale } = useI18n()
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
const months = computed(() => Array.from({ length: 12 }, (_, index) => new Intl.DateTimeFormat(locale.value, { month: 'short' }).format(new Date(2026, index, 1))))
const requests = computed(() => [
  { name: t('showcase.charts.thisYear'), values: [820, 932, 901, 1134, 1290, 1330, 1420, 1380, 1510, 1602, 1688, 1820] },
  { name: t('showcase.charts.lastYear'), values: [620, 712, 701, 834, 890, 930, 1020, 1080, 1010, 1102, 1188, 1240] },
])
const regions = computed(() => ['north', 'south', 'east'].map((value) => t(`showcase.region.${value}`)))
const hosts = computed(() => [{ name: t('showcase.charts.hosts'), values: [42, 28, 35] }])
const quarters = ['Q1', 'Q2', 'Q3', 'Q4']
const usage = computed(() => [
  { name: t('showcase.scenes.cpu'), values: [42, 58, 64, 51] },
  { name: t('showcase.scenes.memory'), values: [61, 66, 72, 86] },
])
const percent = (value: number) => `${value}%`
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseCharts')" :description="t('showcase.desc.charts')" :trail="trail" />
    <PageSection :cols="4" :title="t('showcase.charts.requests')" :description="t('showcase.charts.requestsText')">
      <TrendChart :label="t('showcase.charts.requests')" :labels="months" :series="requests" />
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.charts.byRegion')" :description="t('showcase.charts.byRegionText')">
      <TrendChart type="bar" :label="t('showcase.charts.byRegion')" :labels="regions" :series="hosts" />
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.charts.usage')" :description="t('showcase.charts.usageText')">
      <TrendChart type="bar" :label="t('showcase.charts.usage')" :labels="quarters" :series="usage" :format="percent" />
    </PageSection>
  </CardGrid>
</template>
