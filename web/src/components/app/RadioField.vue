<script setup lang="ts" generic="T extends string">
import { RadioGroupIndicator, RadioGroupItem, RadioGroupRoot } from 'reka-ui'
import { useId } from 'vue'

// 单选组: 2 到 5 个互斥选项且都要一眼看到时用(选项带说明时尤其合适); 选项很短且不超过 5 个也可用 SegmentedControl, 6 到 10 个用 SelectMenu.
// 每项: 左边 16 px 圆点(点击区域 24 px), 与标签文字上下居中, 右边标签, 可选说明在标签下面. 放在 FormField(group)里.
defineProps<{ options: { value: T; label: string; description?: string }[]; label: string; disabled?: boolean }>()
const model = defineModel<T>({ required: true })
const prefix = useId()
</script>

<template>
  <RadioGroupRoot v-model="model" data-control :aria-label="label" :disabled="disabled" class="flex flex-col gap-2">
    <div v-for="option in options" :key="option.value" data-choice class="flex items-start gap-1">
      <RadioGroupItem
        :id="`${prefix}-${option.value}`"
        :value="option.value"
        data-choice-control
        :aria-describedby="option.description ? `${prefix}-${option.value}-description` : undefined"
        class="group -ml-1 flex size-6 shrink-0 items-center justify-center rounded-full outline-none disabled:opacity-50"
      >
        <span class="flex size-4 items-center justify-center rounded-full border border-input bg-card transition-colors group-data-[state=checked]:border-primary">
          <RadioGroupIndicator class="block size-2 rounded-full bg-primary" />
        </span>
      </RadioGroupItem>
      <div class="flex min-w-0 flex-col">
        <label :for="`${prefix}-${option.value}`" data-choice-label class="text-sm font-medium">{{ option.label }}</label>
        <p v-if="option.description" :id="`${prefix}-${option.value}-description`" class="text-sm text-muted-foreground">{{ option.description }}</p>
      </div>
    </div>
  </RadioGroupRoot>
</template>
