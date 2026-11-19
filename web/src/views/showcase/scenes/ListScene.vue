<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormField from '@/components/app/FormField.vue'
import SelectMenu from '@/components/app/SelectMenu.vue'
import { Input } from '@/components/ui/input'
import PageHeader from '@/components/app/PageHeader.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import PageSection from '@/components/app/PageSection.vue'

// 场景: 数据列表. 一张整行卡片: 筛选字段在上, 表格在中间, 分页在下面(超过 10 行必须分页).
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const keyword = ref('')
const region = ref<string>()
const regions = computed(() => ['north', 'south', 'east'].map((value) => ({ value, label: t(`showcase.region.${value}`) })))
const columns = computed(() => [
  { key: 'name', label: t('showcase.table.name') },
  { key: 'address', label: t('showcase.table.address'), mono: true },
  { key: 'requests', label: t('showcase.table.requests'), align: 'end' as const },
])
const all = Array.from({ length: 25 }, (_, i) => ({ id: i + 1, name: `host-${i + 1}`, address: `192.168.1.${20 + i}`, requests: (i + 1) * 137 }))
const matched = computed(() => all.filter((row) => row.name.includes(keyword.value.trim())))
const PAGE_SIZE = 10
const page = ref(1)
const rows = computed(() => matched.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))
watch(keyword, () => (page.value = 1))
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesList')" :description="t('showcase.scenes.desc.list')" :trail="trail" />
    <!-- 列表: 一张整行卡片, 上面是筛选(搜索和地区), 下面是表格 -->
    <PageSection :cols="4" :title="t('showcase.table.title')">
      <FormField v-slot="field" :label="t('showcase.scenes.search')" :span="8">
        <Input :id="field.id" v-model="keyword" type="search" :placeholder="t('showcase.scenes.searchPlaceholder')" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.regionLabel')" :span="4">
        <SelectMenu :id="field.id" v-model="region" :options="regions" :label="t('showcase.regionLabel')" :placeholder="t('showcase.regionPlaceholder')" />
      </FormField>
      <DataTable :columns="columns" :rows="rows" row-key="id" :caption="t('showcase.table.title')" :empty="t('showcase.empty')" />
      <PaginationBar v-model="page" :total="matched.length" :page-size="PAGE_SIZE" />
    </PageSection>
  </CardGrid>
</template>
