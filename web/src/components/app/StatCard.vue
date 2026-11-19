<script setup lang="ts">
import { ArrowDownRight, ArrowUpRight } from '@lucide/vue'
import StatusBadge from './StatusBadge.vue'
import Sparkline from './Sparkline.vue'
import { type CardLayout, cardAttrs } from './cardLayout'

// 数据卡: 仪表板上的一个指标: 名称(灰), 大号数值, 变化(涨跌标签和说明), 可选趋势线. 一行 4 张(默认 1 列宽), 同一行的数据卡内容结构一致.
// trend 为正数显示绿色上箭头, 负数显示红色下箭头(涨跌的好坏由页面用 good 指定: 默认涨是好事).
const props = withDefaults(defineProps<{ label: string; value: string; delta: number; deltaLabel: string; trend?: number[]; good?: 'up' | 'down' } & CardLayout>(), { good: 'up' })
const positive = props.delta >= 0
const tone = (positive ? 'up' : 'down') === props.good ? 'success' : 'destructive'
</script>

<template>
  <section data-reflow data-card data-card-body data-layout="stat-card" v-bind="cardAttrs(props)" class="rounded-lg border border-border bg-card text-card-foreground shadow-sm">
    <p class="text-sm text-muted-foreground">{{ label }}</p>
    <p class="text-3xl font-semibold tabular-nums">{{ value }}</p>
    <div class="flex flex-wrap items-center gap-2 text-sm">
      <StatusBadge :tone="tone">
        <component :is="positive ? ArrowUpRight : ArrowDownRight" class="mr-1 size-4" aria-hidden="true" />
        {{ Math.abs(delta) }}%
      </StatusBadge>
      <span class="text-muted-foreground">{{ deltaLabel }}</span>
    </div>
    <Sparkline v-if="trend" :values="trend" :label="label" />
  </section>
</template>
