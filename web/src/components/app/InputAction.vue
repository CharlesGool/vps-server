<script setup lang="ts">
import type { Component } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

// 输入框加提交按钮的复合控件, 整体占满所在栏; 放在 FormField 中, 并在 <form> 内使用. 其余属性传给输入框.
defineOptions({ inheritAttrs: false })
defineProps<{ actionLabel: string; actionIcon?: Component; actionDisabled?: boolean }>()
const model = defineModel<string>({ default: '' })
</script>

<template>
  <div data-control="field" class="flex gap-2">
    <Input v-bind="$attrs" v-model="model" />
    <Button type="submit" variant="outline" class="shrink-0" :disabled="actionDisabled">
      <component :is="actionIcon" v-if="actionIcon" aria-hidden="true" />
      {{ actionLabel }}
    </Button>
  </div>
</template>
