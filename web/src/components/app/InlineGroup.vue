<script setup lang="ts">
// 一行排列的一组小元素(状态标签, 小图标), 放不下时换行; 卡片里的一个块. 元素之间 8 px.
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <slot />
  </div>
</template>
