<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

// 辅助线: 只在开发服务器和视觉测试构建中挂载(见 App.vue). 按 G 键或在地址后加 ?grid 显示/隐藏.
// 蓝色是页面的列(列之间的空白是 24 px 间距); 绿色是每张卡片内的 12 栏(栏之间 16 px 间距), 块的左右边缘贴在栏上; 红色虚线是每个块的上下边缘.
interface Line {
  x: number
  y: number
  w: number
  h: number
  kind: 'page' | 'column' | 'block'
}
const visible = ref(new URLSearchParams(location.search).has('grid'))
const lines = ref<Line[]>([])
let timer = 0

// 栅格的每一栏: 从计算样式读出栏宽和间距
function tracks(el: Element) {
  const style = getComputedStyle(el)
  const widths = style.gridTemplateColumns.split(' ').map(Number.parseFloat)
  const gap = Number.parseFloat(style.columnGap) || 0
  const rect = el.getBoundingClientRect()
  let x = rect.left + el.clientLeft + (Number.parseFloat(style.paddingLeft) || 0)
  return widths.map((width) => {
    const track = { x, width }
    x += width + gap
    return track
  })
}

function measure() {
  const found: Line[] = []
  const sx = window.scrollX
  const sy = window.scrollY
  for (const cells of document.querySelectorAll('[data-card-cells]')) {
    if (!cells.checkVisibility()) continue
    const rect = cells.getBoundingClientRect()
    for (const track of tracks(cells)) found.push({ x: track.x + sx, y: rect.top + sy, w: track.width, h: rect.height, kind: 'page' })
  }
  for (const body of document.querySelectorAll('[data-card-body]')) {
    if (!body.checkVisibility()) continue
    const rect = body.getBoundingClientRect()
    const style = getComputedStyle(body)
    const top = rect.top + (Number.parseFloat(style.paddingTop) || 0) + sy
    const height = rect.height - (Number.parseFloat(style.paddingTop) || 0) - (Number.parseFloat(style.paddingBottom) || 0)
    const columns = tracks(body)
    for (const track of columns) found.push({ x: track.x + sx, y: top, w: track.width, h: height, kind: 'column' })
    const left = columns[0]?.x ?? rect.left
    const right = (columns.at(-1)?.x ?? rect.right) + (columns.at(-1)?.width ?? 0)
    for (const block of body.querySelectorAll(':scope > *')) {
      if (!block.checkVisibility()) continue
      const blockRect = block.getBoundingClientRect()
      found.push({ x: left + sx, y: blockRect.top + sy, w: right - left, h: 0, kind: 'block' })
      found.push({ x: left + sx, y: blockRect.bottom + sy, w: right - left, h: 0, kind: 'block' })
    }
  }
  lines.value = found
}

function onKeydown(event: KeyboardEvent) {
  const target = event.target instanceof HTMLElement ? event.target : null
  if (target?.closest('input, textarea, [contenteditable], [role="combobox"]')) return
  if (event.key.toLowerCase() === 'g' && !event.ctrlKey && !event.metaKey && !event.altKey) visible.value = !visible.value
}

watch(
  visible,
  (on) => {
    window.clearInterval(timer)
    if (on) {
      measure()
      timer = window.setInterval(measure, 200)
    }
  },
  { immediate: true },
)
onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  window.clearInterval(timer)
})

const STYLE: Record<Line['kind'], string> = {
  page: 'border border-primary/40 bg-primary/5',
  column: 'border-x border-success/50 bg-success/5',
  block: 'border-t border-dashed border-destructive/60',
}
</script>

<template>
  <div v-if="visible" aria-hidden="true" data-grid-overlay class="pointer-events-none absolute top-0 left-0 z-50">
    <div
      v-for="(line, index) in lines"
      :key="index"
      class="absolute"
      :class="STYLE[line.kind]"
      :style="{ left: `${line.x}px`, top: `${line.y}px`, width: `${line.w}px`, height: `${line.h}px` }"
    />
  </div>
</template>
