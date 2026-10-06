<script setup lang="ts">
import { CircleAlert, CircleCheck, Info, X } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { closeToast, toast } from '@/lib/toast'

const { t } = useI18n()

const icon = computed(() => {
  if (toast.value?.tone === 'success') return { is: CircleCheck, class: 'text-success' }
  if (toast.value?.tone === 'destructive') return { is: CircleAlert, class: 'text-destructive' }
  return { is: Info, class: 'text-primary' }
})
</script>

<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex justify-end" role="status" aria-live="polite">
      <Transition name="toast">
        <div
          v-if="toast"
          class="pointer-events-auto flex min-h-19 w-full max-w-toast items-center gap-3 rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-lg"
        >
          <component :is="icon.is" class="size-5 shrink-0" :class="icon.class" aria-hidden="true" />
          <p class="flex-1 text-sm">{{ toast.text }}</p>
          <Button variant="ghost" size="icon" :aria-label="t('action.close')" @click="closeToast">
            <X aria-hidden="true" />
          </Button>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<style scoped>
/* 只有进入动画; 关闭立即生效 */
.toast-enter-active {
  transform-origin: bottom right;
  transition:
    opacity var(--duration-toast) var(--ease-out),
    transform var(--duration-toast) var(--ease-out);
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(var(--toast-enter-offset)) scale(var(--toast-enter-scale));
}
</style>
