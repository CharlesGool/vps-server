<script setup lang="ts">
import { ChevronDown } from '@lucide/vue'
import { AccordionContent, AccordionHeader, AccordionItem, AccordionRoot, AccordionTrigger } from 'reka-ui'
import { type BlockLayout, blockAttrs } from './cardLayout'

// 折叠面板: 一组可以展开和收起的段落(常见问题, 高级选项). 整组有外框, 每项一行标题(h3, 和卡片内小标题一样是 14 px; 高 48 px, 右侧箭头), 相邻项之间有分隔线.
// 每项的内容放在与 value 同名的插槽里; multiple 允许同时展开多项, 默认一次只展开一项. 不要用它藏必填字段.
const props = defineProps<{ items: { value: string; title: string }[]; multiple?: boolean; defaultValue?: string | string[] } & BlockLayout>()
</script>

<template>
  <AccordionRoot
    v-bind="blockAttrs(props)"
    :type="multiple ? 'multiple' : 'single'"
    :default-value="defaultValue"
    collapsible
    data-accordion
    class="flex flex-col divide-y divide-border rounded-md border border-border"
  >
    <AccordionItem v-for="item in items" :key="item.value" :value="item.value">
      <AccordionHeader as="h3" class="text-sm">
        <AccordionTrigger
          class="group flex h-12 w-full items-center justify-between gap-2 px-4 text-left font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          {{ item.title }}
          <ChevronDown class="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" aria-hidden="true" />
        </AccordionTrigger>
      </AccordionHeader>
      <AccordionContent class="px-4 pb-4 text-muted-foreground">
        <slot :name="item.value" />
      </AccordionContent>
    </AccordionItem>
  </AccordionRoot>
</template>
