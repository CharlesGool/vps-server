// vps-server: 随附的 xterm.js(/static/third_party/xterm/, 不经打包). 第一次用时加载样式和两个脚本.
export interface XTerminal {
  cols: number
  rows: number
  open(element: HTMLElement): void
  write(data: Uint8Array): void
  reset(): void
  focus(): void
  dispose(): void
  resize(cols: number, rows: number): void
  loadAddon(addon: unknown): void
  onData(listener: (data: string) => void): void
}
export interface XFitAddon {
  proposeDimensions(): { cols: number; rows: number } | undefined
}
declare global {
  interface Window {
    Terminal?: new (options: Record<string, unknown>) => XTerminal
    FitAddon?: { FitAddon: new () => XFitAddon }
  }
}

const BASE = '/static/third_party/xterm/'
function script(name: string) {
  return new Promise<void>((resolve, reject) => {
    const element = document.createElement('script')
    element.src = BASE + name
    element.onload = () => resolve()
    element.onerror = () => reject(new Error(name))
    document.head.append(element)
  })
}
let loading: Promise<void> | undefined
export function loadXterm() {
  loading ??= (async () => {
    if (!document.querySelector(`link[href="${BASE}xterm.css"]`)) {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = BASE + 'xterm.css'
      document.head.append(link)
    }
    if (!window.Terminal) await script('xterm.js')
    if (!window.FitAddon) await script('addon-fit.js')
  })().catch((err) => {
    loading = undefined
    throw err
  })
  return loading
}
