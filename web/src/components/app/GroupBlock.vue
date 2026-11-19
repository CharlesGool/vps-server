<script setup lang="ts">
import { type BlockLayout, blockAttrs } from './cardLayout'

// 卡片里带小标题的一组内容, 如变更日志里的"新增", "修复". 小标题是 h3; span 指定栏数, 几组可以并排.
const props = defineProps<{ title: string } & BlockLayout>()
</script>

<template>
  <section v-bind="blockAttrs(props)" class="flex flex-col gap-2">
    <h3 class="text-sm font-semibold text-muted-foreground">{{ title }}</h3>
    <slot />
  </section>
</template>
