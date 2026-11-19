<script setup lang="ts">
import { CircleAlert, CircleCheck, Info, X } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { closeToast, pauseToast, toast } from '@/lib/toast'

const { t } = useI18n()

// 顶部居中, 按类型着色: 成功, 失败, 提示
const tone = computed(() => {
  if (toast.value?.tone === 'success') {
    return { icon: CircleCheck, class: 'border-success bg-success-surface text-success-on-surface' }
  }
  if (toast.value?.tone === 'destructive') {
    return { icon: CircleAlert, class: 'border-destructive bg-destructive-surface text-destructive-on-surface' }
  }
  return { icon: Info, class: 'border-primary bg-accent text-accent-foreground' }
})
</script>

<template>
  <Teleport to="body">
    <!-- 新旧通知叠在同一格里: 替换时旧通知还要留一帧, 并排会把新通知挤偏 -->
    <div class="pointer-events-none fixed inset-x-4 top-4 z-50 grid justify-items-center" role="status" aria-live="polite">
      <Transition name="toast">
        <div
          v-if="toast"
          :key="toast.id"
          data-toast
          :data-tone="toast.tone"
          class="pointer-events-auto col-start-1 row-start-1 flex min-h-24 w-full max-w-toast items-center gap-4 rounded-lg border-2 p-5 shadow-lg"
          :class="tone.class"
          @pointerenter="pauseToast(true)"
          @pointerleave="pauseToast(false)"
          @focusin="pauseToast(true)"
          @focusout="pauseToast(false)"
        >
          <component :is="tone.icon" class="size-8 shrink-0" aria-hidden="true" />
          <div class="flex min-w-0 flex-1 flex-col gap-1">
            <p class="text-lg font-semibold">{{ toast.title }}</p>
            <p v-if="toast.description" class="text-base">{{ toast.description }}</p>
          </div>
          <button
            type="button"
            class="flex size-9 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-card"
            :aria-label="t('action.close')"
            @click="closeToast"
          >
            <X class="size-5" aria-hidden="true" />
          </button>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<style scoped>
/* 只有进入动画; 关闭立即生效 */
.toast-enter-active {
  transform-origin: top center;
  transition:
    opacity var(--duration-toast) var(--ease-out),
    transform var(--duration-toast) var(--ease-out);
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(var(--toast-enter-offset)) scale(var(--toast-enter-scale));
}
</style>
