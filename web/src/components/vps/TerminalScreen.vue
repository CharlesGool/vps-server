<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import { loadXterm, type XTerminal } from '@/lib/xterm'

// vps-server 项目组件: 浏览器终端(xterm.js 经 /terminal/ws 连接 PTY). 宽度随卡片, 列数按宽度算;
// 高度固定 30 行(不由页面设置尺寸), 内容多时在终端内滚动. 颜色取当前主题的卡片背景和前景色. token 由 /api/terminal 给出.
const props = defineProps<{ token: string; label: string }>()
const { t } = useI18n()
const screen = ref<HTMLElement>()
const disconnected = ref(false)
const ROWS = 30
let terminal: XTerminal | undefined
let socket: WebSocket | undefined
let observer: ResizeObserver | undefined
let leaving = false

onMounted(async () => {
  try {
    await loadXterm()
  } catch {
    disconnected.value = true
    return
  }
  if (leaving || !screen.value || !window.Terminal || !window.FitAddon) return
  // xterm 只认 rgb 等常见写法, 而标记是 oklch: 取终端框计算后的背景色和文字色(bg-muted, text-foreground), 经画布换成十六进制
  const box = getComputedStyle(screen.value)
  const canvas = document.createElement('canvas').getContext('2d')
  const toHex = (value: string) => {
    if (!canvas) return value
    canvas.clearRect(0, 0, 1, 1)
    canvas.fillStyle = value
    canvas.fillRect(0, 0, 1, 1)
    const [r, g, b] = canvas.getImageData(0, 0, 1, 1).data
    return '#' + [r, g, b].map((part) => (part ?? 0).toString(16).padStart(2, '0')).join('')
  }
  const mono = getComputedStyle(document.documentElement).getPropertyValue('--font-mono').trim()
  terminal = new window.Terminal({
    cursorBlink: true,
    scrollback: 5000,
    fontSize: 14,
    rows: ROWS,
    fontFamily: mono || 'monospace',
    theme: { background: toHex(box.backgroundColor), foreground: toHex(box.color), cursor: toHex(box.color) },
  })
  const fit = new window.FitAddon.FitAddon()
  terminal.loadAddon(fit)
  terminal.open(screen.value)
  // xterm.css 给滚动层写死了黑色背景; 改成透明, 露出终端框的背景色
  const viewport = screen.value.querySelector<HTMLElement>('.xterm-viewport')
  if (viewport) viewport.style.backgroundColor = 'transparent'
  const resize = () => {
    const size = fit.proposeDimensions()
    if (!terminal || !size || !Number.isFinite(size.cols)) return
    terminal.resize(Math.max(20, size.cols), ROWS)
    if (socket?.readyState === WebSocket.OPEN && terminal.cols <= 400) socket.send(JSON.stringify({ type: 'resize', cols: terminal.cols, rows: terminal.rows }))
  }
  observer = new ResizeObserver(resize)
  observer.observe(screen.value)
  terminal.onData((data) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'input', data }))
  })
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const next = new WebSocket(`${protocol}//${location.host}/terminal/ws?token=${encodeURIComponent(props.token)}`)
  socket = next
  next.binaryType = 'arraybuffer'
  next.onopen = () => {
    resize()
    terminal?.focus()
  }
  next.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) terminal?.write(new Uint8Array(event.data))
  }
  next.onclose = () => {
    if (!leaving) disconnected.value = true
  }
})
onBeforeUnmount(() => {
  leaving = true
  observer?.disconnect()
  socket?.close()
  terminal?.dispose()
})
</script>

<template>
  <AlertBanner v-if="disconnected" tone="warning">{{ t('console.terminal_disconnected') }}</AlertBanner>
  <div ref="screen" :aria-label="label" class="overflow-hidden rounded-md border border-border bg-muted p-2 text-foreground" />
</template>
