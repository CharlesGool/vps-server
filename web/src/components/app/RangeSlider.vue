<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { cssDuration, easeOutCubic, reducedMotion } from '@/lib/motion'

const props = withDefaults(defineProps<{ label: string; min?: number; max?: number; step?: number }>(), {
  min: 0,
  max: 100,
  step: 1,
})
const model = defineModel<number>({ required: true })

const track = ref<HTMLElement>()
const thumb = ref<HTMLElement>()
// display 是视觉位置; 点击轨道的缓动过程中它与 model 不同步.
const display = ref(model.value)
const percent = computed(() => ((display.value - props.min) / (props.max - props.min)) * 100)
let frame = 0
let dragging = false

watch(model, (value) => {
  if (!frame && !dragging) display.value = value
})

function clamp(value: number) {
  const stepped = Math.round((value - props.min) / props.step) * props.step + props.min
  return Math.min(props.max, Math.max(props.min, stepped))
}

function valueAt(clientX: number) {
  const rect = track.value!.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
  return props.min + ratio * (props.max - props.min)
}

function setNow(value: number) {
  cancelAnimationFrame(frame)
  frame = 0
  model.value = clamp(value)
  display.value = model.value
}

// 点击轨道: 以 --duration-slider 缓动到点击位置
function animateTo(target: number) {
  cancelAnimationFrame(frame)
  const duration = cssDuration('--duration-slider')
  if (reducedMotion() || duration === 0) return setNow(target)
  const from = display.value
  const to = clamp(target)
  const start = performance.now()
  const tick = (now: number) => {
    const t = Math.min(1, (now - start) / duration)
    display.value = from + (to - from) * easeOutCubic(t)
    model.value = clamp(display.value)
    frame = t < 1 ? requestAnimationFrame(tick) : 0
  }
  frame = requestAnimationFrame(tick)
}

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  // 阻止默认的 mousedown 焦点转移, 让键盘继续操作滑块
  event.preventDefault()
  track.value!.setPointerCapture(event.pointerId)
  dragging = true
  thumb.value!.focus()
  if (event.target === thumb.value) setNow(valueAt(event.clientX))
  else animateTo(valueAt(event.clientX))
}

// 拖动立即跟随, 并取消进行中的缓动
function onPointerMove(event: PointerEvent) {
  if (dragging && track.value!.hasPointerCapture(event.pointerId)) setNow(valueAt(event.clientX))
}

function onPointerUp() {
  dragging = false
}

function onKeydown(event: KeyboardEvent) {
  const big = Math.max(props.step, (props.max - props.min) / 10)
  const delta: Record<string, number> = {
    ArrowRight: props.step,
    ArrowUp: props.step,
    ArrowLeft: -props.step,
    ArrowDown: -props.step,
    PageUp: big,
    PageDown: -big,
  }
  if (event.key in delta) setNow(model.value + delta[event.key]!)
  else if (event.key === 'Home') setNow(props.min)
  else if (event.key === 'End') setNow(props.max)
  else return
  event.preventDefault()
}

onBeforeUnmount(() => cancelAnimationFrame(frame))
</script>

<template>
  <div
    ref="track"
    class="relative flex h-6 w-full cursor-pointer touch-none select-none items-center"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <div class="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
      <div class="absolute inset-y-0 left-0 bg-primary" :style="{ width: `${percent}%` }" />
    </div>
    <div
      ref="thumb"
      role="slider"
      tabindex="0"
      :aria-label="label"
      :aria-valuemin="min"
      :aria-valuemax="max"
      :aria-valuenow="model"
      class="absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary bg-card shadow-sm"
      :style="{ left: `${percent}%` }"
      @keydown="onKeydown"
    />
  </div>
</template>
