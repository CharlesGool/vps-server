<script setup lang="ts">
import { type CardLayout, cardAttrs } from './cardLayout'

// 页面卡片: 页面上所有控件都放在卡片里, 一张卡片是一个模块(一个表单, 一组设置, 一张表). 高度由内容决定.
// 标题默认是 h2; 没有页头的页面(登录页)用 heading 为 h1 的卡片标题作为页面标题. cols, rows, col 见 cardLayout.ts.
// 子元素是卡片内栅格的块: 默认占满一行; FormField 等用 span 指定栏数, 按钮用 FormActions, 设置项用 SettingRow.
// 标题旁的说明图标用 info 插槽, 标题上方的内容(如登录卡的图标)用 lead 插槽.
const props = withDefaults(defineProps<{ title?: string; description?: string; as?: 'section' | 'article' | 'div'; heading?: 'h1' | 'h2' } & CardLayout>(), { as: 'section', heading: 'h2' })
</script>

<template>
  <component
    :is="as"
    data-reflow
    data-card
    data-card-body
    data-layout="card"
    v-bind="cardAttrs(props)"
    class="rounded-lg border border-border bg-card text-card-foreground shadow-sm"
  >
    <slot name="lead" />
    <div v-if="title" data-card-title class="flex items-center gap-2">
      <component :is="heading" :class="heading === 'h1' ? 'text-2xl font-semibold' : 'text-lg font-semibold'">{{ title }}</component>
      <slot name="info" />
    </div>
    <p v-if="description" data-card-description class="text-sm text-muted-foreground">{{ description }}</p>
    <slot />
  </component>
</template>
