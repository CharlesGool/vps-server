<script setup lang="ts">
// 按钮行: 直接放在 PageSection 或 AppDialog 中, 通常是卡片的最后一块. 按钮宽度随文字(不小于 96 px), 默认靠右, 主按钮放最后;
// align="start" 时靠左(如卡片中间的操作). block 时每个按钮占满一行, 只用于登录卡这类窄卡片的主要操作.
// 一张卡片最多一个主按钮(默认样式), 其他用 outline 或 secondary. 没有边框也没有底色的文字按钮不允许使用.
defineProps<{ align?: 'start' | 'end'; block?: boolean }>()
</script>

<template>
  <div data-form-actions :data-align="align" :data-block="block ? '' : undefined">
    <slot />
  </div>
</template>
