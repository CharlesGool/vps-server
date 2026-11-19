<script setup lang="ts">
import { Minus, Plus } from '@lucide/vue'
import { NumberFieldDecrement, NumberFieldIncrement, NumberFieldInput, NumberFieldRoot } from 'reka-ui'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

// 数字输入: 左边减, 中间输入(可直接键入, 方向键和滚轮也能改), 右边加; unit 是数值后面的单位(如 MB, 秒). 值超出 min, max 时自动收回范围内.
// 放在 FormField 里, 标签用 id 关联. 替代 <input type="number">.
// grouping: 是否按语言加千位分隔符(默认加); 端口, 编号这类数值设为 false.
withDefaults(defineProps<{ min?: number; max?: number; step?: number; unit?: string; id?: string; disabled?: boolean; grouping?: boolean }>(), {
  grouping: true,
})
const model = defineModel<number>({ default: 0 })
const { t } = useI18n()
</script>

<template>
  <NumberFieldRoot v-model="model" :min="min" :max="max" :step="step ?? 1" :disabled="disabled" :format-options="{ useGrouping: grouping }" data-control="field" class="flex h-10 items-center gap-1 rounded-md border border-input bg-card px-1 focus-within:border-ring">
    <NumberFieldDecrement as-child>
      <Button variant="secondary" size="icon-sm" class="w-8" :aria-label="t('component.decrease')"><Minus aria-hidden="true" /></Button>
    </NumberFieldDecrement>
    <NumberFieldInput :id="id" class="h-full min-w-0 flex-1 bg-transparent px-2 text-center text-sm tabular-nums outline-none" />
    <span v-if="unit" class="text-sm text-muted-foreground">{{ unit }}</span>
    <NumberFieldIncrement as-child>
      <Button variant="secondary" size="icon-sm" class="w-8" :aria-label="t('component.increase')"><Plus aria-hidden="true" /></Button>
    </NumberFieldIncrement>
  </NumberFieldRoot>
</template>
