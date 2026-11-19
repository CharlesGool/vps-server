<script setup lang="ts">
import { ChevronDown, Ellipsis } from '@lucide/vue'
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuRoot, DropdownMenuSeparator, DropdownMenuTrigger } from 'reka-ui'
import { Button } from '@/components/ui/button'

// 操作菜单: 一个按钮点开, 里面是一组操作(编辑, 复制, 删除...). 表格每行末尾用 icon-only(三个点的图标按钮, label 作无障碍名称); 按钮行里用带文字的触发按钮.
// 菜单项 danger 为红字, 放在最后并用分隔线隔开; 危险操作选中后**必须**再弹出 ConfirmDialog 确认, 不能直接执行. 选中项通过 select 事件给出 key.
defineProps<{ label: string; items: { key: string; label: string; danger?: boolean }[]; iconOnly?: boolean }>()
const emit = defineEmits<{ select: [key: string] }>()
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger as-child>
      <Button v-if="iconOnly" variant="outline" size="icon-sm" class="w-8" :aria-label="label"><Ellipsis aria-hidden="true" /></Button>
      <Button v-else variant="outline">{{ label }}<ChevronDown aria-hidden="true" /></Button>
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent align="end" :side-offset="4" class="z-50 min-w-40 overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md">
        <template v-for="(item, index) in items" :key="item.key">
          <DropdownMenuSeparator v-if="item.danger && index > 0 && !items[index - 1]?.danger" class="my-1 h-px bg-border" />
          <DropdownMenuItem
            class="flex h-10 cursor-pointer items-center rounded-sm px-2 text-sm outline-none select-none data-highlighted:bg-accent data-highlighted:text-accent-foreground"
            :class="item.danger && 'text-destructive'"
            @select="emit('select', item.key)"
          >
            {{ item.label }}
          </DropdownMenuItem>
        </template>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
