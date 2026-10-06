<template>
  <div class="card-grid">
    <slot />
  </div>
</template>

<style scoped>
@reference "../../styles/main.css";

/* 卡片集合: 窄屏最多 3 列, lg 起最多 6 列; 每行(含最后一行)均分宽度, 不留空列 */
.card-grid {
  --card-columns: 3;
  --card-gap: calc(var(--spacing) * 4);
  display: flex;
  flex-wrap: wrap;
  gap: var(--card-gap);

  @variant lg {
    --card-columns: 6;
  }
}
.card-grid > :deep(*) {
  flex: 1 1 var(--card-min-width);
  min-width: min(
    100%,
    max(var(--card-min-width), calc((100% - (var(--card-columns) - 1) * var(--card-gap)) / var(--card-columns)))
  );
}
</style>
