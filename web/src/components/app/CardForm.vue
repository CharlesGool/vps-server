<script setup lang="ts">
// 把多张相邻卡片连成一个表单: 内容太多放不进一张卡片的表单拆成几张卡片, 外面包一个 CardForm. 自身不占格, 只放在 CardGrid 中.
// @submit 等监听直接写在组件上.
</script>

<template>
  <form data-form-scope data-layout="form-scope">
    <slot />
  </form>
</template>
