<script setup lang="ts">
import { X } from '@lucide/vue'
import { TagsInputInput, TagsInputItem, TagsInputItemDelete, TagsInputItemText, TagsInputRoot } from 'reka-ui'
import { useI18n } from 'vue-i18n'

// 标签输入: 键入后按回车或逗号添加一个标签, 点标签上的 × 或在空输入框按退格删除; 自由文本, 如关键字, 邮箱列表. 固定的候选项用 ComboboxField multiple.
// 保持单行高度 40 px: 标签多时在框内横向滚动. 放在 FormField 里.
defineProps<{ placeholder?: string; id?: string; max?: number }>()
const model = defineModel<string[]>({ default: () => [] })
const { t } = useI18n()
</script>

<template>
  <TagsInputRoot v-model="model" data-control="field" :max="max" add-on-paste delimiter="," class="flex h-10 items-center gap-1 overflow-x-auto rounded-md border border-input bg-card px-1 focus-within:border-ring">
    <TagsInputItem v-for="tag in model" :key="tag" :value="tag" class="flex h-8 shrink-0 items-center gap-1 rounded-sm bg-secondary pl-2 text-sm text-secondary-foreground">
      <TagsInputItemText />
      <TagsInputItemDelete aria-labelledby="" class="flex size-6 items-center justify-center rounded-sm hover:bg-accent" :aria-label="t('component.removeTag', { name: tag })">
        <X class="size-4" aria-hidden="true" />
      </TagsInputItemDelete>
    </TagsInputItem>
    <TagsInputInput :id="id" :placeholder="placeholder" class="h-full min-w-24 flex-1 bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground" />
  </TagsInputRoot>
</template>
