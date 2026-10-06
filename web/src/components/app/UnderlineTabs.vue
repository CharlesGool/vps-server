<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

export interface TabItem {
  value: string
  label: string
}

const props = defineProps<{ tabs: TabItem[]; label: string }>()
const model = defineModel<string>({ required: true })

const id = useId()
const list = ref<HTMLElement>()
const labels = ref<HTMLElement[]>([])
const buttons = ref<HTMLButtonElement[]>([])
const indicator = ref({ x: 0, width: 0 })
const ready = ref(false)

// 下划线与所选标签文字同宽同位, 翻译或重排后重新测量.
function measure() {
  const index = props.tabs.findIndex((tab) => tab.value === model.value)
  const text = labels.value[index]
  if (!list.value || !text) return
  const listRect = list.value.getBoundingClientRect()
  const textRect = text.getBoundingClientRect()
  indicator.value = { x: textRect.left - listRect.left, width: textRect.width }
}

function select(index: number, focus = false) {
  const tab = props.tabs[index]
  if (!tab) return
  model.value = tab.value
  if (focus) buttons.value[index]?.focus()
}

function onKeydown(event: KeyboardEvent) {
  const current = props.tabs.findIndex((tab) => tab.value === model.value)
  const last = props.tabs.length - 1
  const next: Record<string, number> = {
    ArrowRight: current === last ? 0 : current + 1,
    ArrowLeft: current === 0 ? last : current - 1,
    Home: 0,
    End: last,
  }
  if (event.key in next) {
    event.preventDefault()
    select(next[event.key]!, true)
  }
}

let observer: ResizeObserver | undefined
onMounted(() => {
  measure()
  requestAnimationFrame(() => (ready.value = true))
  observer = new ResizeObserver(measure)
  if (list.value) observer.observe(list.value)
  for (const el of labels.value) observer.observe(el)
})
onBeforeUnmount(() => observer?.disconnect())
watch([model, () => props.tabs], () => nextTick(measure), { deep: true })
</script>

<template>
  <div>
    <div class="relative">
      <div ref="list" role="tablist" :aria-label="label" class="flex gap-6 border-b border-border" @keydown="onKeydown">
        <button data-ui-control
          v-for="(tab, index) in tabs"
          :id="`${id}-tab-${tab.value}`"
          :key="tab.value"
          ref="buttons"
          type="button"
          role="tab"
          :aria-selected="tab.value === model"
          :aria-controls="`${id}-panel`"
          :tabindex="tab.value === model ? 0 : -1"
          class="tab py-3 text-sm font-medium"
          :class="tab.value === model ? 'text-primary' : 'text-muted-foreground hover:text-foreground'"
          @click="select(index)"
        >
          <span ref="labels">{{ tab.label }}</span>
        </button>
      </div>
      <span
        class="indicator pointer-events-none absolute bottom-0 left-0 bg-primary"
        :class="{ animated: ready }"
        :style="{ width: `${indicator.width}px`, transform: `translateX(${indicator.x}px)` }"
        aria-hidden="true"
      />
    </div>
    <div :id="`${id}-panel`" role="tabpanel" :aria-labelledby="`${id}-tab-${model}`" class="pt-4">
      <slot :active="model" />
    </div>
  </div>
</template>

<style scoped>
.tab {
  transition: color var(--duration-tab) var(--ease-standard);
}
.indicator {
  height: var(--tab-indicator-height);
}
.indicator.animated {
  transition:
    transform var(--duration-tab) var(--ease-standard),
    width var(--duration-tab) var(--ease-standard);
}
</style>
