<script setup lang="ts">
import { onBeforeUnmount, onMounted, onUpdated, ref } from 'vue'
import { type CardLayout, cardAttrs } from './cardLayout'

// 页面卡片: 页面上所有控件都放在卡片里, 一张卡片是一个模块(一个表单, 一组设置, 一张表). 高度由内容决定.
// 标题默认是 h2; 没有页头的页面(登录页)用 heading 为 h1 的卡片标题作为页面标题. cols, rows, col 见 cardLayout.ts.
// 子元素是卡片内栅格的块: 默认占满一行; FormField 等用 span 指定栏数, 按钮用 FormActions, 设置项用 SettingRow.
// 标题旁的说明图标用 info 插槽, 标题上方的内容(如登录卡的图标)用 lead 插槽.
const props = withDefaults(defineProps<{ title?: string; description?: string; as?: 'section' | 'article' | 'div'; heading?: 'h1' | 'h2' } & CardLayout>(), { as: 'section', heading: 'h2' })

// 卡片最后一块是按钮行时, 按钮行贴在卡片底部: 同一行卡片等高, 它们的按钮因此在同一水平线上.
// 卡片内栅格的行数由内容决定, 只靠样式无法让"最后一行"吃掉剩余高度, 所以数出按钮行之前的内容占几行,
// 再把按钮行放进其后一行可伸展的行里.
const root = ref<{ $el?: Element } | Element>()
let observer: ResizeObserver | undefined
function element(): HTMLElement | undefined {
  const value = root.value
  const el = value instanceof Element ? value : value?.$el
  return el instanceof HTMLElement ? el : undefined
}
function placeActions() {
  const el = element()
  if (!el) return
  const children = [...el.children].filter((child): child is HTMLElement => child instanceof HTMLElement && child.getClientRects().length > 0)
  const last = children.at(-1)
  for (const child of el.children) if (child !== last && child instanceof HTMLElement && child.dataset.actionsEnd !== undefined) clearActions(el, child)
  if (!last || !last.matches('[data-form-actions]:not([data-block])') || children.length < 2) {
    if (last) clearActions(el, last)
    return
  }
  const tops = new Set(children.slice(0, -1).map((child) => Math.round(child.offsetTop)))
  const rows = `repeat(${tops.size}, auto) 1fr`
  if (el.style.gridTemplateRows !== rows) el.style.gridTemplateRows = rows
  if (last.style.gridRow !== String(tops.size + 1)) last.style.gridRow = String(tops.size + 1)
  last.style.alignSelf = 'end'
  last.dataset.actionsEnd = ''
}
function clearActions(el: HTMLElement, actions: HTMLElement) {
  if (actions.dataset.actionsEnd === undefined) return
  el.style.removeProperty('grid-template-rows')
  actions.style.removeProperty('grid-row')
  actions.style.removeProperty('align-self')
  delete actions.dataset.actionsEnd
}
onMounted(() => {
  placeActions()
  const el = element()
  if (el && typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(() => placeActions())
    observer.observe(el)
  }
})
onUpdated(placeActions)
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <component
    :is="as"
    ref="root"
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
