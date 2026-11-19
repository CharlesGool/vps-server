<script setup lang="ts">
import { type BlockLayout, blockAttrs } from './cardLayout'

// 搜索结果列表: 每条一个链接标题(主题色), 下面一行灰色的位置(路径或类型), 再下面一段摘要; 条目之间有分隔线.
// highlight 是搜索词, 标题和摘要中匹配的部分加底色标出(不区分大小写). 没有结果时页面改放 EmptyState, 不显示空列表.
export interface SearchResult {
  key: string
  title: string
  to: string
  meta?: string
  snippet?: string
}
const props = defineProps<{ items: SearchResult[]; highlight?: string } & BlockLayout>()

function parts(text: string) {
  const word = props.highlight?.trim()
  if (!word) return [{ text, match: false }]
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text
    .split(new RegExp(`(${escaped})`, 'gi'))
    .filter(Boolean)
    .map((piece) => ({ text: piece, match: piece.toLowerCase() === word.toLowerCase() }))
}
</script>

<template>
  <ul v-bind="blockAttrs(props)" data-result-list class="flex flex-col divide-y divide-border">
    <li v-for="item in items" :key="item.key" class="flex flex-col py-3 first:pt-0 last:pb-0">
      <RouterLink :to="item.to" class="w-fit font-medium text-primary hover:underline">
        <template v-for="(piece, index) in parts(item.title)" :key="index">
          <mark v-if="piece.match" class="rounded-sm bg-warning-surface text-warning-on-surface">{{ piece.text }}</mark>
          <template v-else>{{ piece.text }}</template>
        </template>
      </RouterLink>
      <span v-if="item.meta" class="text-sm text-muted-foreground">{{ item.meta }}</span>
      <p v-if="item.snippet" class="text-sm">
        <template v-for="(piece, index) in parts(item.snippet)" :key="index">
          <mark v-if="piece.match" class="rounded-sm bg-warning-surface text-warning-on-surface">{{ piece.text }}</mark>
          <template v-else>{{ piece.text }}</template>
        </template>
      </p>
    </li>
  </ul>
</template>
