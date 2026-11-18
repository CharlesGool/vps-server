<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'
import { type TextareaVariants, textareaVariants } from '.'

const props = defineProps<{ size?: TextareaVariants['size']; class?: HTMLAttributes['class'] }>()
const model = defineModel<string>({ default: '' })
</script>

<template>
  <textarea v-model="model" data-slot="textarea" data-control="area" :class="cn(textareaVariants({ size }), props.class)" />
</template>
