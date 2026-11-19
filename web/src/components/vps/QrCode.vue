<script setup lang="ts">
import { ref, watch } from 'vue'
import LoadingState from '@/components/app/LoadingState.vue'
import { qrSvg } from '@/lib/qrcode'

// vps-server 项目组件: 文本的二维码, 宽度随所在栏, 最大 256 px. 库生成的 SVG 自带白底黑码(扫码需要高对比度, 不随主题变色). label 是读屏名称.
const props = defineProps<{ text: string; label: string }>()
const svg = ref('')
const failed = ref(false)
watch(
  () => props.text,
  async (text) => {
    svg.value = ''
    failed.value = false
    if (!text) return
    try {
      svg.value = await qrSvg(text)
    } catch {
      failed.value = true
    }
  },
  { immediate: true },
)
</script>

<template>
  <LoadingState v-if="!svg && !failed" />
  <!-- 库生成的 SVG 只含 path 和 rect, 由文本计算得出 -->
  <div v-else-if="svg" role="img" :aria-label="label" class="mx-auto w-full max-w-64 overflow-hidden rounded-md" v-html="svg" />
</template>
