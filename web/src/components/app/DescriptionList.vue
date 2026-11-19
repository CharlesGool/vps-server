<script setup lang="ts">
import { type BlockLayout, blockAttrs } from './cardLayout'
import CopyButton from './CopyButton.vue'

// 描述列表: 详情页里只读的"名称: 值"列表, 左边名称(灰色), 右边值(右对齐, 可用 value-<key> 插槽放状态标签, 链接, 等宽文本), 相邻行之间有分隔线.
// copyable 的值旁边加复制按钮(地址, 编号). 编辑用 FormField, 设置用 SettingRow, 只读展示用本组件, 三者不混用.
const props = defineProps<{ items: { key: string; label: string; value?: string; mono?: boolean; copyable?: boolean }[] } & BlockLayout>()
</script>

<template>
  <dl v-bind="blockAttrs(props)" class="flex flex-col divide-y divide-border">
    <div v-for="item in items" :key="item.key" class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2 first:pt-0 last:pb-0">
      <dt class="text-muted-foreground">{{ item.label }}</dt>
      <dd class="flex min-w-0 items-center justify-end gap-2 text-right" :class="item.mono && 'font-mono'">
        <slot :name="`value-${item.key}`" :item="item">{{ item.value }}</slot>
        <CopyButton v-if="item.copyable && item.value" icon-only :value="item.value" :label="`${$t('component.copy')} ${item.label}`" />
      </dd>
    </div>
  </dl>
</template>
