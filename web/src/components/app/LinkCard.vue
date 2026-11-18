<script setup lang="ts">
import { ChevronRight } from '@lucide/vue'
import type { Component } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { type CardLayout, cardAttrs } from './cardLayout'

// 指向其他页面的入口卡片, 放在 CardGrid 中, 默认占 1 列; 仪表板的功能入口使用它.
const props = defineProps<{ to: RouteLocationRaw; title: string; description?: string; icon: Component } & CardLayout>()
</script>

<template>
  <RouterLink
    :to="to"
    data-reflow
    data-card
    data-card-body
    data-layout="link-card"
    v-bind="cardAttrs(props)"
    class="group rounded-lg border border-border bg-card shadow-sm transition-colors hover:border-primary"
  >
    <span class="flex items-center justify-between">
      <span class="flex size-10 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
        <component :is="icon" class="size-5" aria-hidden="true" />
      </span>
      <ChevronRight class="size-5 shrink-0 text-muted-foreground group-hover:text-primary" aria-hidden="true" />
    </span>
    <span class="text-lg font-semibold">{{ title }}</span>
    <span v-if="description" class="text-sm text-muted-foreground">{{ description }}</span>
  </RouterLink>
</template>
