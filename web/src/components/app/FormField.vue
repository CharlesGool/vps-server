<script setup lang="ts">
import { computed, useId } from 'vue'
import { type BlockLayout, blockAttrs } from './cardLayout'

// 表单字段: 标签在上, 控件, 说明, 错误提示依次向下. 页面中每个带标签的控件都用它包裹, 并直接放在 PageSection 中; span 是占的栏数(1 到 12), start 是起始栏, rows 是占的行数.
// 默认插槽参数 { id, describedby, invalid } 绑定到控件的 id, aria-describedby, aria-invalid(或组件的同名属性).
// group: 控件不是单个可标记元素(如 SegmentedControl)时设为 true, 标签改为组标题.
// hide-label: 卡片标题已经说明字段含义时只对读屏显示标签; 同一行不能和有标签的字段混用.
const props = withDefaults(
  defineProps<{ label: string; help?: string; error?: string; group?: boolean; hideLabel?: boolean } & BlockLayout>(),
  { span: 12 },
)

const id = useId()
const describedby = computed(
  () => [props.help ? `${id}-help` : '', props.error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined,
)
</script>

<template>
  <div
    data-form-field
    v-bind="blockAttrs(props)"
    :data-label-hidden="hideLabel ? '' : undefined"
    :data-form-field-group="group ? '' : undefined"
    :role="group ? 'group' : undefined"
    :aria-labelledby="group ? `${id}-label` : undefined"
    class="flex flex-col gap-2"
  >
    <span v-if="group" :id="`${id}-label`" class="text-sm font-medium" :class="hideLabel && 'sr-only'">{{ label }}</span>
    <label v-else :for="id" class="text-sm font-medium" :class="hideLabel && 'sr-only'">{{ label }}</label>
    <slot :id="id" :describedby="describedby" :invalid="error ? true : undefined" />
    <p v-if="help" :id="`${id}-help`" class="text-sm text-muted-foreground">{{ help }}</p>
    <p v-if="error" :id="`${id}-error`" role="alert" class="text-sm text-destructive">{{ error }}</p>
  </div>
</template>
