<script setup lang="ts">
import { SearchX } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import FormField from '@/components/app/FormField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import ResultList from '@/components/app/ResultList.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { Input } from '@/components/ui/input'

// 场景: 搜索结果. 一张整行卡片: 上面是搜索框和类型筛选, 然后是结果数量, 结果列表(匹配的文字标出), 最下面分页;
// 没有结果时列表换成 EmptyState, 说明怎么调整搜索. 输入即搜索, 不需要搜索按钮.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
type Kind = 'all' | 'host' | 'doc'
const keyword = ref('host')
const kind = ref<Kind>('all')
const kinds = computed(() => (['all', 'host', 'doc'] as const).map((value) => ({ value, label: t(`showcase.search.${value}`) })))
const all = computed(() => [
  ...Array.from({ length: 9 }, (_, i) => ({
    key: `host-${i + 1}`,
    kind: 'host' as const,
    title: `host-${i + 1}`,
    to: '/scenes/detail',
    meta: `${t('showcase.search.host')} · 192.168.1.${20 + i}`,
    snippet: t('showcase.search.hostSnippet', { n: i + 1 }),
  })),
  ...['deploy', 'backup', 'network', 'access'].map((topic) => ({
    key: topic,
    kind: 'doc' as const,
    title: t(`showcase.search.docs.${topic}.title`),
    to: '/changelog',
    meta: `${t('showcase.search.doc')} · ${t('page.changelog')}`,
    snippet: t(`showcase.search.docs.${topic}.snippet`),
  })),
])
const matched = computed(() => {
  const word = keyword.value.trim().toLowerCase()
  return all.value.filter((item) => (kind.value === 'all' || item.kind === kind.value) && (!word || `${item.title} ${item.snippet}`.toLowerCase().includes(word)))
})
const PAGE_SIZE = 5
const page = ref(1)
const rows = computed(() => matched.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))
watch([keyword, kind], () => (page.value = 1))
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesSearch')" :description="t('showcase.scenes.desc.search')" :trail="trail" />
    <PageSection :cols="4" :title="t('showcase.search.title')" :description="t('showcase.search.titleText')">
      <FormField v-slot="field" :label="t('showcase.scenes.search')" :span="8">
        <Input :id="field.id" v-model="keyword" type="search" :placeholder="t('showcase.scenes.searchPlaceholder')" />
      </FormField>
      <FormField :label="t('showcase.search.kind')" :span="4" group>
        <SegmentedControl v-model="kind" :options="kinds" :label="t('showcase.search.kind')" />
      </FormField>
      <p class="text-sm text-muted-foreground" role="status">{{ t('showcase.search.count', { count: matched.length }) }}</p>
      <ResultList v-if="matched.length" :items="rows" :highlight="keyword" />
      <EmptyState v-else :icon="SearchX" :title="t('showcase.search.none')" :description="t('showcase.search.noneText')" />
      <PaginationBar v-if="matched.length > PAGE_SIZE" v-model="page" :total="matched.length" :page-size="PAGE_SIZE" />
    </PageSection>
  </CardGrid>
</template>
