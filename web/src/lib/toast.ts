import { ref } from 'vue'
import { cssDuration } from './motion'

export interface ToastMessage {
  id: number
  text: string
  tone: 'default' | 'success' | 'destructive'
}

export const toast = ref<ToastMessage | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined
let nextId = 1

// 同一时间只显示一条; 再次触发时替换内容并重新计时.
export function showToast(text: string, tone: ToastMessage['tone'] = 'default') {
  toast.value = { id: nextId++, text, tone }
  clearTimeout(timer)
  timer = setTimeout(closeToast, cssDuration('--toast-lifetime'))
}

export function closeToast() {
  clearTimeout(timer)
  toast.value = null
}
