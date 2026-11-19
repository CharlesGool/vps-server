<script setup lang="ts">
import {
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
  AlertDialogTrigger,
} from 'reka-ui'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

// 确认对话框: 删除, 重置, 注销其他会话这类不可恢复或影响大的操作**必须**先确认. 标题说明要做什么, 说明写后果; 左边"取消", 右边确认按钮.
// danger 时确认按钮是危险样式(红). 点遮罩或按 Esc 等于取消. 确认后触发 confirm 事件. trigger 插槽放触发按钮.
defineProps<{ title: string; description: string; confirmLabel: string; danger?: boolean }>()
const emit = defineEmits<{ confirm: [] }>()
const open = defineModel<boolean>('open', { default: false })
const { t } = useI18n()
</script>

<template>
  <AlertDialogRoot v-model:open="open">
    <AlertDialogTrigger v-if="$slots.trigger" as-child>
      <slot name="trigger" />
    </AlertDialogTrigger>
    <AlertDialogPortal>
      <AlertDialogOverlay class="fixed inset-0 z-50 bg-overlay" />
      <AlertDialogContent
        data-card-body
        class="fixed top-1/2 left-1/2 z-50 max-h-full w-full max-w-dialog -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-border bg-card text-card-foreground shadow-lg"
      >
        <AlertDialogTitle class="text-lg font-semibold">{{ title }}</AlertDialogTitle>
        <AlertDialogDescription class="text-sm text-muted-foreground">{{ description }}</AlertDialogDescription>
        <div data-form-actions>
          <AlertDialogCancel as-child>
            <Button variant="outline">{{ t('component.cancel') }}</Button>
          </AlertDialogCancel>
          <AlertDialogAction as-child>
            <Button :variant="danger ? 'destructive' : 'default'" @click="emit('confirm')">{{ confirmLabel }}</Button>
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
