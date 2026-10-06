<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { reducedMotion } from '@/lib/motion'

// 两个及以上设置组: 左侧分区导航, 窄屏时位于内容上方.
// 宽屏时导航随页面滚动保持在视口内的原位置: 它不是硬性的 sticky, 而是缓动地飘向目标位置.
const props = defineProps<{ sections: { id: string; label: string }[]; label: string }>()
const current = ref(props.sections[0]?.id)
const host = ref<HTMLElement>()
const nav = ref<HTMLElement>()
let observer: IntersectionObserver | undefined
let frame = 0
let offset = 0
let target = 0

const FOLLOW_TOP = 24 // 与内容区上内边距一致 (px)
const EASE = 0.14 // 每帧向目标靠近的比例

function jump(id: string) {
  current.value = id
  document.getElementById(id)?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' })
}

function wide() {
  return matchMedia('(min-width: 48rem)').matches
}

function measure() {
  const el = nav.value
  const layout = host.value?.closest('.settings-layout') ?? host.value?.parentElement
  if (!el || !layout) return
  if (!wide()) {
    target = 0
    return
  }
  const room = layout.getBoundingClientRect()
  target = Math.min(Math.max(FOLLOW_TOP - room.top, 0), Math.max(room.height - el.offsetHeight, 0))
}

function paint() {
  frame = 0
  const el = nav.value
  if (!el) return
  offset = reducedMotion() || !wide() ? target : offset + (target - offset) * EASE
  if (Math.abs(target - offset) < 0.4) offset = target
  el.style.transform = offset ? `translateY(${offset}px)` : ''
  if (offset !== target) frame = requestAnimationFrame(paint)
}

function follow() {
  measure()
  if (!frame) frame = requestAnimationFrame(paint)
}

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
      if (visible.length) current.value = visible[0]!.target.id
    },
    { rootMargin: '0px 0px -60% 0px' },
  )
  for (const section of props.sections) {
    const el = document.getElementById(section.id)
    if (el) observer.observe(el)
  }
  window.addEventListener('scroll', follow, { passive: true })
  window.addEventListener('resize', follow)
  follow()
})
onBeforeUnmount(() => {
  observer?.disconnect()
  window.removeEventListener('scroll', follow)
  window.removeEventListener('resize', follow)
  if (frame) cancelAnimationFrame(frame)
})
</script>

<template>
  <div ref="host" class="mb-6 md:mb-0">
    <nav ref="nav" :aria-label="label" class="will-change-transform">
      <ul class="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
        <li v-for="section in sections" :key="section.id" class="flex-none">
          <a
            :href="`#${section.id}`"
            class="flex h-9 items-center whitespace-nowrap rounded-md px-3 text-sm font-medium transition-colors"
            :class="current === section.id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground'"
            :aria-current="current === section.id ? 'location' : undefined"
            @click.prevent="jump(section.id)"
          >
            {{ section.label }}
          </a>
        </li>
      </ul>
    </nav>
  </div>
</template>
