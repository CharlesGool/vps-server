<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { Input, type InputVariants } from '@/components/ui/input'

// 密码输入框: 带文字标签的显示/隐藏按钮, 按钮在输入框内部右侧. 切换不改变值, 不提交表单, 不移走焦点; 组件卸载即恢复遮盖.
defineOptions({ inheritAttrs: false })
const props = defineProps<{ size?: InputVariants['size'] }>()
const model = defineModel<string>({ default: '' })
const visible = ref(false)
const { t } = useI18n()
</script>

<template>
  <div data-control="field" class="relative">
    <Input v-bind="$attrs" v-model="model" :size="size" :type="visible ? 'text' : 'password'" spellcheck="false" class="pr-12" />
    <Button
      type="button"
      variant="secondary"
      size="sm"
      class="absolute right-1 px-2"
      :class="props.size === 'lg' ? 'top-2' : 'top-1'"
      :aria-pressed="visible"
      @mousedown.prevent
      @click="visible = !visible"
    >
      {{ visible ? t('action.hide') : t('action.show') }}
    </Button>
  </div>
</template>
