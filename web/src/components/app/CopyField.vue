<script setup lang="ts">
import { Input } from '@/components/ui/input'
import CopyButton from './CopyButton.vue'

// 只读值加复制按钮(API 密钥, 访问地址): 放在 FormField 中(id 传字段的 id), 整体占满所在栏; 值用等宽字体, 不能编辑.
defineProps<{ value: string; id?: string }>()
</script>

<template>
  <div data-control="field" class="flex gap-2">
    <Input :id="id" :model-value="value" readonly class="font-mono" />
    <CopyButton :value="value" />
  </div>
</template>
