<script setup lang="ts">
import { X } from '@lucide/vue'
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle, DialogTrigger } from 'reka-ui'
import { useI18n } from 'vue-i18n'

// 侧边抽屉: 从右侧滑出, 宽 400 px(手机上占满), 高度占满窗口. 用于不离开当前页面查看或编辑一条记录的详情(内容比对话框多时).
// 分三段: 顶部标题和说明, 中间内容(12 栏栅格, 内容多时只有这一段滚动), 底部按钮行(footer 插槽, 主操作在最右). 确认操作和短表单用 AppDialog.
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
      <DialogContent data-drawer class="fixed inset-y-0 right-0 z-50 flex w-full max-w-drawer flex-col border-l border-border bg-card text-card-foreground shadow-lg">
        <div data-card-body class="border-b border-border">
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
        </div>
        <div data-card-body class="min-h-0 flex-1 overflow-y-auto">
          <slot />
        </div>
        <div v-if="$slots.footer" data-card-body class="border-t border-border">
          <div data-form-actions>
            <slot name="footer" />
          </div>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
