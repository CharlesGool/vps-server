<script setup lang="ts">
import { Check } from '@lucide/vue'
import { CheckboxIndicator, CheckboxRoot } from 'reka-ui'
import { useId } from 'vue'
import { type BlockLayout, blockAttrs } from './cardLayout'

// 带文字标签的复选框: 左边 16 px 方框(点击区域 24 px), 与标签文字上下居中, 右边标签. 协议类勾选项不加说明,
// 协议正文用 label 插槽写成标签里的链接(如"我已阅读并接受《使用条款》"); 其他勾选项需要时可加说明. 属于表单样式(标签在上的 FormField 那一类),
// 用于需要提交的勾选项; 立即生效的设置用 SwitchField. 同一张卡片里**不能**和 SwitchField, SettingRow 混用. 替代原生 checkbox.
const props = defineProps<{ label: string; description?: string; disabled?: boolean } & BlockLayout>()
const model = defineModel<boolean>({ default: false })
const id = useId()
</script>

<template>
  <div data-control data-form-style data-choice v-bind="blockAttrs(props)" class="flex items-start gap-1">
    <!-- 点击区域 24 px, 里面的方框 16 px, 与标签文字上下居中; 点击区域向左多出 4 px, 方框左边缘与其他字段对齐 -->
    <CheckboxRoot
      :id="id"
      v-model="model"
      :disabled="disabled"
      :aria-describedby="description ? `${id}-description` : undefined"
      data-choice-control
      class="group -ml-1 flex size-6 shrink-0 items-center justify-center rounded-sm disabled:opacity-50"
    >
      <span
        class="flex size-4 items-center justify-center rounded-sm border border-input bg-card text-primary-foreground transition-colors group-data-[state=checked]:border-primary group-data-[state=checked]:bg-primary"
      >
        <CheckboxIndicator>
          <Check class="size-3" aria-hidden="true" />
        </CheckboxIndicator>
      </span>
    </CheckboxRoot>
    <div class="flex min-w-0 flex-col">
      <label :for="id" data-choice-label class="text-sm font-medium">
        <slot name="label">{{ label }}</slot>
      </label>
      <p v-if="description" :id="`${id}-description`" class="text-sm text-muted-foreground">{{ description }}</p>
    </div>
  </div>
</template>
