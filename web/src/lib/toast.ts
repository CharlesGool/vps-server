import { ref } from 'vue'
import { cssDuration } from './motion'

export interface ToastMessage {
  id: number
  title: string
  description?: string
  tone: 'default' | 'success' | 'destructive'
}

export const toast = ref<ToastMessage | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined
let nextId = 1
let paused = false

// 失败消息停留更久
function lifetime(tone: ToastMessage['tone']) {
  return cssDuration(tone === 'destructive' ? '--toast-lifetime-error' : '--toast-lifetime')
}

function schedule() {
  clearTimeout(timer)
  if (toast.value && !paused) timer = setTimeout(closeToast, lifetime(toast.value.tone))
}

// 同一时间只显示一条; 再次触发时替换内容并重新计时.
export function showToast(title: string, tone: ToastMessage['tone'] = 'default', description?: string) {
  toast.value = { id: nextId++, title, description, tone }
  schedule()
}

export function closeToast() {
  clearTimeout(timer)
  paused = false
  toast.value = null
}

// 悬停或键盘焦点在通知上时暂停自动关闭; 离开后重新计时.
export function pauseToast(value: boolean) {
  paused = value
  schedule()
}
