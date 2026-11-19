<script setup lang="ts">
import { computed, useId } from 'vue'

// 设置项: 设置页模块卡片里的一行, 左边是名称和说明, 右边是控件(最宽 320 px); 窄卡片里控件换到下一行. 相邻设置行之间有分隔线.
// 属于设置行样式, 同一张卡片里不能和 FormField, CheckboxField 混用. error 显示在说明下面.
// 默认插槽参数 { id, describedby } 绑定到控件. group: 控件不是单个可标记元素(如 SegmentedControl)时设为 true.
const props = defineProps<{ label: string; description?: string; group?: boolean; error?: string }>()
const id = useId()
const describedby = computed(() => [props.description ? `${id}-description` : '', props.error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined)
</script>

<template>
  <div
    data-setting-row
    data-row-style
    :role="group ? 'group' : undefined"
    :aria-labelledby="group ? `${id}-label` : undefined"
    class="flex flex-wrap items-center justify-between gap-x-6 gap-y-2"
  >
    <div class="setting-text flex min-w-0 flex-col">
      <span v-if="group" :id="`${id}-label`" data-row-label class="font-medium">{{ label }}</span>
      <label v-else :for="id" data-row-label class="font-medium">{{ label }}</label>
      <p v-if="description" :id="`${id}-description`" class="text-sm text-muted-foreground">{{ description }}</p>
      <p v-if="error" :id="`${id}-error`" role="alert" class="text-sm text-destructive">{{ error }}</p>
    </div>
    <div class="setting-control">
      <slot :id="id" :describedby="describedby" :invalid="error ? true : undefined" />
    </div>
  </div>
</template>

<style scoped>
@reference "../../styles/main.css";

.setting-text {
  flex: 1 1 calc(var(--card-min-width) * 0.75);
}
.setting-control {
  flex: 0 1 var(--container-control);
  min-width: 0;
}
</style>
