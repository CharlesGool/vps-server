<script setup lang="ts">
import { SwitchRoot, SwitchThumb } from 'reka-ui'
import { useId } from 'vue'
import { type BlockLayout, blockAttrs } from './cardLayout'

// 立即生效的开关设置: 左边标签和说明, 右边开关, 开关与标签第一行上下居中. 属于设置行样式(与 SettingRow 一样, 相邻行之间有分隔线),
// 同一张卡片里**不能**和 FormField, CheckboxField 混用. 替代原生 checkbox 和"开/关"两项分段控件.
const props = defineProps<{ label: string; description?: string; disabled?: boolean } & BlockLayout>()
const model = defineModel<boolean>({ default: false })
const id = useId()
</script>

<template>
  <div data-control data-row-style data-choice v-bind="blockAttrs(props)" class="flex items-start justify-between gap-4">
    <div class="flex min-w-0 flex-col">
      <label :for="id" data-choice-label data-row-label class="font-medium">{{ label }}</label>
      <p v-if="description" :id="`${id}-description`" class="text-sm text-muted-foreground">{{ description }}</p>
    </div>
    <!-- 开关与标签第一行上下居中 -->
    <span class="flex h-6 shrink-0 items-center">
    <SwitchRoot
      :id="id"
      v-model="model"
      :disabled="disabled"
      :aria-describedby="description ? `${id}-description` : undefined"
      data-choice-control
      class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-transparent bg-input transition-colors disabled:opacity-50 data-[state=checked]:bg-primary"
    >
      <SwitchThumb
        class="block size-5 rounded-full bg-card shadow-sm transition-transform data-[state=checked]:translate-x-5"
      />
    </SwitchRoot>
    </span>
  </div>
</template>
