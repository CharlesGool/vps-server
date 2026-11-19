<script setup lang="ts">
// 页面唯一的顶层布局: 卡片栅格. 每页恰有一个 CardGrid, 直接子元素只能是 PageHeader, PageSection, LinkCard, StatCard 或包着卡片的 CardForm.
// 列数 1, 2, 4 和间距由样式按容器宽度决定(见 styles/main.css). 卡片占整数列(cols), 可跨几行(rows), 可指定起始列(col); 卡片高度由内容决定, 同一行等高.
// 卡片之间不重叠, 多列布局中除最后一行外每行排满.
</script>

<template>
  <div data-card-grid data-layout="card-grid">
    <div data-card-cells>
      <slot />
    </div>
  </div>
</template>
