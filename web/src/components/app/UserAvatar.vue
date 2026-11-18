<script setup lang="ts">
import { AvatarFallback, AvatarImage, AvatarRoot } from 'reka-ui'
import { computed } from 'vue'

// 头像: 圆形, 有图片显示图片, 没有或加载失败时显示名字的前两个字母(中文取最后一个字). size 只有 sm(32 px, 表格和列表里)和 md(40 px, 详情和顶栏).
// 头像旁边总要有名字: show-name 在右边显示名字(表格和列表里用这种), 否则名字只给读屏. 图片本身对读屏隐藏(alt 为空).
const props = withDefaults(defineProps<{ name: string; src?: string; size?: 'sm' | 'md'; showName?: boolean }>(), { size: 'sm' })
const initials = computed(() => {
  const name = props.name.trim()
  if (/[㐀-鿿]/.test(name)) return name.slice(-1)
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join('')
})
</script>

<template>
  <span data-avatar class="inline-flex min-w-0 items-center gap-2">
    <AvatarRoot class="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary text-secondary-foreground" :class="size === 'sm' ? 'size-8 text-sm' : 'size-10'">
      <AvatarImage v-if="src" :src="src" alt="" class="size-full object-cover" />
      <AvatarFallback aria-hidden="true" class="font-medium">{{ initials }}</AvatarFallback>
    </AvatarRoot>
    <span :class="showName ? 'truncate' : 'sr-only'">{{ name }}</span>
  </span>
</template>
