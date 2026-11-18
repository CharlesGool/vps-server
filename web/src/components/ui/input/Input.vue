<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'
import { type InputVariants, inputVariants } from '.'

const props = defineProps<{ size?: InputVariants['size']; class?: HTMLAttributes['class'] }>()
const model = defineModel<string>({ default: '' })
</script>

<template>
  <input v-model="model" data-slot="input" data-control="field" :class="cn(inputVariants({ size }), props.class)" />
</template>
