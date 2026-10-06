<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { reducedMotion } from '@/lib/motion'

// 两个及以上设置组: 左侧分区导航, 窄屏时位于内容上方.
const props = defineProps<{ sections: { id: string; label: string }[]; label: string }>()
const current = ref(props.sections[0]?.id)
let observer: IntersectionObserver | undefined

function jump(id: string) {
  current.value = id
  document.getElementById(id)?.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' })
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
})
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <nav :aria-label="label" class="md:sticky md:top-6">
    <ul class="flex flex-wrap gap-1 md:flex-col">
      <li v-for="section in sections" :key="section.id">
        <a
          :href="`#${section.id}`"
          class="flex h-9 items-center rounded-md px-3 text-sm font-medium transition-colors"
          :class="current === section.id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground'"
          :aria-current="current === section.id ? 'location' : undefined"
          @click.prevent="jump(section.id)"
        >
          {{ section.label }}
        </a>
      </li>
    </ul>
  </nav>
</template>
