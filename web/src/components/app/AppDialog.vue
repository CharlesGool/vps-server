<script setup lang="ts">
import { X } from '@lucide/vue'
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle, DialogTrigger } from 'reka-ui'
import { useI18n } from 'vue-i18n'

// 模态对话框: 确认操作和短表单. 标题必填; 内容区同卡片的 12 栏栅格; 操作按钮放 footer 插槽, 一行 1 到 4 个, 主操作在最右. 替代原生 <dialog> 和自写遮罩层.
defineProps<{ title: string; description?: string }>()
const open = defineModel<boolean>('open', { default: false })
const { t } = useI18n()
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogTrigger v-if="$slots.trigger" as-child>
      <slot name="trigger" />
    </DialogTrigger>
    <DialogPortal>
      <DialogOverlay class="fixed inset-0 z-50 bg-overlay" />
      <DialogContent
        data-card-body
        class="fixed top-1/2 left-1/2 z-50 max-h-full w-full max-w-dialog -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-border bg-card text-card-foreground shadow-lg"
      >
        <div class="flex items-center justify-between gap-2">
          <DialogTitle class="text-lg font-semibold">{{ title }}</DialogTitle>
          <DialogClose
            class="flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            :aria-label="t('action.close')"
          >
            <X class="size-4" aria-hidden="true" />
          </DialogClose>
        </div>
        <DialogDescription v-if="description" class="text-sm text-muted-foreground">{{ description }}</DialogDescription>
        <slot />
        <div v-if="$slots.footer" data-form-actions>
          <slot name="footer" />
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
