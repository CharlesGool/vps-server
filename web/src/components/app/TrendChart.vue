<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { type BlockLayout, blockAttrs } from './cardLayout'

// 图表: 折线图(type="line", 看趋势)或柱状图(type="bar", 比较各项), 高 256 px, 宽度占满所在栏. 只用于有坐标轴的正式图表; 数据卡里的小趋势线用 Sparkline.
// 横轴是 labels(最多 12 个), 纵轴从 0 开始自动取整刻度(最多 5 格). 每组数据一种颜色(chart-1 到 chart-4, 最多 4 组), 多于一组时下方显示图例.
// 鼠标移到(手机上点按)某一项上显示这一项的数值. 图形对读屏隐藏, 另附只给读屏的数据表; label 是图表名称(必填), format 格式化数值(如加单位).
const props = withDefaults(
  defineProps<{ label: string; labels: string[]; series: { name: string; values: number[] }[]; type?: 'line' | 'bar'; format?: (value: number) => string } & BlockLayout>(),
  { type: 'line', format: (value: number) => value.toLocaleString() },
)
const COLORS = [
  { stroke: 'stroke-chart-1', fill: 'fill-chart-1', bg: 'bg-chart-1' },
  { stroke: 'stroke-chart-2', fill: 'fill-chart-2', bg: 'bg-chart-2' },
  { stroke: 'stroke-chart-3', fill: 'fill-chart-3', bg: 'bg-chart-3' },
  { stroke: 'stroke-chart-4', fill: 'fill-chart-4', bg: 'bg-chart-4' },
]
// 绘图区四周留给坐标轴文字的空间(px); 高度和 h-64 一致
const HEIGHT = 256
const LEFT = 48
const RIGHT = 8
const TOP = 12
const BOTTOM = 32
// 纵轴最多 5 格
const MAX_TICKS = 5

const box = ref<HTMLElement>()
const width = ref(0)
let observer: ResizeObserver | undefined
onMounted(() => {
  observer = new ResizeObserver(([entry]) => (width.value = entry!.contentRect.width))
  observer.observe(box.value!)
})
onBeforeUnmount(() => observer?.disconnect())

// 纵轴刻度: 每格取 1, 2, 2.5, 5 乘 10 的幂, 最多 5 格放下最大值, 顶端是最接近最大值的整刻度
const max = computed(() => Math.max(1, ...props.series.flatMap((item) => item.values)))
const step = computed(() => {
  const raw = max.value / MAX_TICKS
  const power = 10 ** Math.floor(Math.log10(raw))
  return [1, 2, 2.5, 5, 10].map((factor) => factor * power).find((value) => value >= raw)!
})
const count = computed(() => Math.max(1, Math.ceil(max.value / step.value)))
const top = computed(() => step.value * count.value)
const plotWidth = computed(() => Math.max(0, width.value - LEFT - RIGHT))
const plotHeight = HEIGHT - TOP - BOTTOM
const y = (value: number) => TOP + plotHeight - (value / top.value) * plotHeight
const ticks = computed(() => Array.from({ length: count.value + 1 }, (_, index) => index * step.value))
// 每一项占一段宽度; 折线的点在段中间, 柱子在段中间并排
const band = computed(() => plotWidth.value / Math.max(1, props.labels.length))
const center = (index: number) => LEFT + band.value * (index + 0.5)
const barWidth = computed(() => Math.min(32, (band.value * 0.6) / props.series.length))
const barX = (index: number, serie: number) => center(index) - (barWidth.value * props.series.length) / 2 + serie * barWidth.value
// 横轴文字放不下时隔几项显示一个(最后一项总是显示); 文字宽度用画布按当前字体量出
const labelWidth = computed(() => {
  const context = document.createElement('canvas').getContext('2d')
  if (!context || !box.value) return 0
  const style = getComputedStyle(box.value)
  context.font = `${style.fontSize} ${style.fontFamily}`
  return Math.max(...props.labels.map((name) => context.measureText(name).width))
})
const every = computed(() => (band.value ? Math.max(1, Math.ceil((labelWidth.value + 8) / band.value)) : 1))
const showLabel = (index: number) => (props.labels.length - 1 - index) % every.value === 0
const line = (values: number[]) => values.map((value, index) => `${center(index)},${y(value)}`).join(' ')

const hover = ref<number>()
// 提示框放在这一项的右边; 后半段的项放左边, 不超出卡片
const tipStyle = computed(() => {
  if (hover.value === undefined) return {}
  const x = center(hover.value)
  return hover.value < props.labels.length / 2 ? { left: `${x + band.value / 2}px` } : { right: `${width.value - x + band.value / 2}px` }
})
</script>

<template>
  <figure v-bind="blockAttrs(props)" data-chart class="flex flex-col gap-2">
    <div ref="box" class="relative h-64 text-sm" @mouseleave="hover = undefined">
      <svg v-if="width" aria-hidden="true" :width="width" :height="HEIGHT" class="block overflow-visible">
        <g v-for="tick in ticks" :key="tick">
          <line :x1="LEFT" :x2="width - RIGHT" :y1="y(tick)" :y2="y(tick)" class="stroke-border" stroke-width="1" />
          <text :x="LEFT - 8" :y="y(tick)" text-anchor="end" dominant-baseline="middle" class="fill-muted-foreground text-sm">{{ format(tick) }}</text>
        </g>
        <text v-for="(name, index) in labels" v-show="showLabel(index)" :key="name" :x="center(index)" :y="HEIGHT - 8" text-anchor="middle" class="fill-muted-foreground text-sm">{{ name }}</text>
        <rect v-if="hover !== undefined" :x="center(hover) - band / 2" :y="TOP" :width="band" :height="plotHeight" class="fill-muted" />
        <template v-if="type === 'bar'">
          <template v-for="(item, serie) in series" :key="item.name">
            <rect
              v-for="(value, index) in item.values"
              :key="index"
              data-chart-mark
              :x="barX(index, serie)"
              :y="y(value)"
              :width="Math.max(1, barWidth - 2)"
              :height="Math.max(0, TOP + plotHeight - y(value))"
              rx="2"
              :class="COLORS[serie]!.fill"
            />
          </template>
        </template>
        <template v-else>
          <g v-for="(item, serie) in series" :key="item.name">
            <polyline :points="line(item.values)" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" :class="COLORS[serie]!.stroke" />
            <circle v-for="(value, index) in item.values" :key="index" data-chart-mark :cx="center(index)" :cy="y(value)" :r="hover === index ? 4 : 2.5" :class="COLORS[serie]!.fill" />
          </g>
        </template>
        <rect v-for="(_, index) in labels" :key="`hit-${index}`" :x="center(index) - band / 2" :y="TOP" :width="band" :height="plotHeight" fill="transparent" @pointerenter="hover = index" @pointerdown="hover = index" />
      </svg>
      <div
        v-if="hover !== undefined"
        aria-hidden="true"
        data-chart-tip
        class="pointer-events-none absolute top-0 z-10 flex flex-col rounded-md border border-border bg-popover px-3 py-1 text-sm text-popover-foreground shadow-md"
        :style="tipStyle"
      >
        <span class="font-medium">{{ labels[hover] }}</span>
        <span v-for="(item, serie) in series" :key="item.name" class="flex items-center gap-2 whitespace-nowrap">
          <span class="size-2 rounded-full" :class="COLORS[serie]!.bg" />
          {{ item.name }}: {{ format(item.values[hover] ?? 0) }}
        </span>
      </div>
    </div>
    <figcaption v-if="series.length > 1" class="flex flex-wrap justify-center gap-x-4 text-sm text-muted-foreground" aria-hidden="true">
      <span v-for="(item, serie) in series" :key="item.name" class="flex items-center gap-2">
        <span class="size-3 rounded-sm" :class="COLORS[serie]!.bg" />
        {{ item.name }}
      </span>
    </figcaption>
    <!-- 表格不支持 overflow, 所以 sr-only 放在外层 div 上, 否则会把页面撑宽 -->
    <div class="sr-only">
      <table>
        <caption>{{ label }}</caption>
        <thead>
          <tr>
            <th scope="col" class="font-medium">{{ label }}</th>
            <th v-for="name in labels" :key="name" scope="col" class="font-medium">{{ name }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in series" :key="item.name">
            <th scope="row" class="font-medium">{{ item.name }}</th>
            <td v-for="(value, index) in item.values" :key="index">{{ format(value) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </figure>
</template>
