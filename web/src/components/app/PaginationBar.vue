<script setup lang="ts">
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { PaginationEllipsis, PaginationList, PaginationListItem, PaginationNext, PaginationPrev, PaginationRoot } from 'reka-ui'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

// 分页: 左边"第 1-10 条, 共 n 条", 右边上一页, 页码, 下一页; 当前页是 secondary 样式. 放在数据表下面; 数据超过 pageSize 条时**必须**分页.
// total 总条数, pageSize 每页条数(默认 10), v-model 当前页(从 1 起).
const props = withDefaults(defineProps<{ total: number; pageSize?: number }>(), { pageSize: 10 })
const page = defineModel<number>({ default: 1 })
const { t } = useI18n()
const from = computed(() => (props.total ? (page.value - 1) * props.pageSize + 1 : 0))
const to = computed(() => Math.min(props.total, page.value * props.pageSize))
</script>

<template>
  <PaginationRoot v-model:page="page" data-control data-pagination :total="total" :items-per-page="pageSize" :sibling-count="1" show-edges class="flex flex-wrap items-center justify-between gap-2">
    <p class="text-sm text-muted-foreground tabular-nums">{{ t('component.pageRange', { from, to, total }) }}</p>
    <PaginationList v-slot="{ items }" class="flex flex-wrap items-center gap-1">
      <PaginationPrev as-child>
        <Button variant="outline" size="icon-sm" class="w-8" :aria-label="t('component.prevPage')"><ChevronLeft aria-hidden="true" /></Button>
      </PaginationPrev>
      <template v-for="(item, index) in items" :key="index">
        <PaginationListItem v-if="item.type === 'page'" :value="item.value" as-child>
          <Button
            :variant="item.value === page ? 'secondary' : 'outline'"
            size="icon-sm"
            class="w-8 tabular-nums"
            :aria-label="t('component.pageNumber', { page: item.value })"
            :aria-current="item.value === page ? 'page' : undefined"
          >
            {{ item.value }}
          </Button>
        </PaginationListItem>
        <PaginationEllipsis v-else :index="index" class="flex size-8 items-center justify-center text-muted-foreground">…</PaginationEllipsis>
      </template>
      <PaginationNext as-child>
        <Button variant="outline" size="icon-sm" class="w-8" :aria-label="t('component.nextPage')"><ChevronRight aria-hidden="true" /></Button>
      </PaginationNext>
    </PaginationList>
  </PaginationRoot>
</template>
