<script setup lang="ts">
import { Check, Copy, Eye, EyeOff } from '@lucide/vue'
import { onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { writeClipboard } from '@/lib/clipboard'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 默认遮住的值(端口, 密码, 命令). 显示时才向服务器取值, 复制时直接取值写入剪贴板, 值不留在页面里.
// source 和 field 是服务器 /api/private-value 的 id 和 field; label 说明这是什么值(给读屏, 也用在按钮名称里).
// copyable: 是否有复制按钮; reveal: 是否能显示(凭据类默认可以显示).
const props = withDefaults(defineProps<{ source: string; field: string; label: string; copyable?: boolean; reveal?: boolean }>(), {
  copyable: true,
  reveal: true,
})
const { t } = useI18n()
const shown = ref<string>()
const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(timer))

const fetchValue = async () => (await api<{ value: string }>(`private-value?id=${encodeURIComponent(props.source)}&field=${encodeURIComponent(props.field)}`)).value

async function toggle() {
  if (shown.value !== undefined) {
    shown.value = undefined
    return
  }
  try {
    shown.value = await fetchValue()
  } catch {
    showToast(t('legacy.private_value_failed'), 'destructive')
  }
}
async function copy() {
  try {
    await writeClipboard(shown.value ?? (await fetchValue()))
    copied.value = true
    clearTimeout(timer)
    timer = setTimeout(() => (copied.value = false), 2000)
    showToast(t('component.copied'), 'success')
  } catch {
    showToast(t('legacy.private_copy_failed'), 'destructive')
  }
}
</script>

<template>
  <span class="flex min-w-0 items-center justify-end gap-2">
    <code class="min-w-0 font-mono text-sm wrap-anywhere">{{ shown ?? '••••••' }}</code>
    <Button
      v-if="reveal"
      type="button"
      variant="outline"
      size="icon-sm"
      class="w-8 shrink-0"
      :aria-label="`${shown === undefined ? t('legacy.login_show_password') : t('legacy.login_hide_password')} ${label}`"
      :aria-pressed="shown !== undefined"
      @click="toggle"
    >
      <EyeOff v-if="shown !== undefined" aria-hidden="true" />
      <Eye v-else aria-hidden="true" />
    </Button>
    <Button v-if="copyable" type="button" variant="outline" size="icon-sm" class="w-8 shrink-0" :aria-label="`${t('component.copy')} ${label}`" @click="copy">
      <Check v-if="copied" aria-hidden="true" />
      <Copy v-else aria-hidden="true" />
    </Button>
  </span>
</template>
