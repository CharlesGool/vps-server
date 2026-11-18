<script setup lang="ts">
import { Check, Copy } from '@lucide/vue'
import { onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { showToast } from '@/lib/toast'

// 复制按钮: 把 value 复制到剪贴板, 图标变成对勾 2 秒并提示"已复制". 默认是带文字的描边按钮; icon-only 是 32 px 的图标按钮(放在只读值旁边, 如描述列表),
// 这时 label 说明复制的是什么(给读屏). 剪贴板接口不可用(非 HTTPS)时退回到旧的复制方法.
const props = defineProps<{ value: string; label?: string; iconOnly?: boolean }>()
const { t } = useI18n()
const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function write(text: string) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text)
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.className = 'fixed opacity-0'
  document.body.append(area)
  area.select()
  const ok = document.execCommand('copy')
  area.remove()
  if (!ok) throw new Error('copy failed')
}

async function copy() {
  try {
    await write(props.value)
    copied.value = true
    clearTimeout(timer)
    timer = setTimeout(() => (copied.value = false), 2000)
    showToast(t('component.copied'), 'success')
  } catch {
    showToast(t('component.copyFailed'), 'destructive')
  }
}
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <Button v-if="iconOnly" type="button" variant="outline" size="icon-sm" class="w-8" :aria-label="label ?? t('component.copy')" data-copy @click="copy">
    <Check v-if="copied" aria-hidden="true" />
    <Copy v-else aria-hidden="true" />
  </Button>
  <Button v-else type="button" variant="outline" class="shrink-0" data-copy @click="copy">
    <Check v-if="copied" aria-hidden="true" />
    <Copy v-else aria-hidden="true" />
    {{ copied ? t('component.copied') : t('component.copy') }}
  </Button>
</template>
