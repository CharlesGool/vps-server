import { nextTick, watch } from 'vue'
import { mode, theme } from './appearance'
import { cssDuration } from './motion'

// 标签页图标跟随当前主题色: 页面专属 SVG 的底色换成 --primary, 符号换成 --primary-foreground.
// 底色和符号色从服务器提供的 SVG 自身读取, 代码里不写死颜色.
const BACKGROUND = /<rect[^>]*\sfill="([^"]+)"/
const SYMBOL = /<g[^>]*\sstroke="([^"]+)"/

let source: { href: string; text: string } | undefined

// --primary 用的是现代色彩函数写法, 用画布换算成图标渲染一定能识别的十六进制颜色.
function resolveColor(name: string): string {
  const probe = document.createElement('span')
  probe.style.color = `var(${name})`
  document.documentElement.append(probe)
  const color = getComputedStyle(probe).color
  probe.remove()
  const context = document.createElement('canvas').getContext('2d', { willReadFrequently: true })
  if (!context) return color
  context.fillStyle = color
  context.fillRect(0, 0, 1, 1)
  const [r, g, b] = context.getImageData(0, 0, 1, 1).data
  return `#${[r, g, b].map((value) => value!.toString(16).padStart(2, '0')).join('')}`
}

async function update() {
  const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) return
  try {
    if (!source) {
      const original = link.getAttribute('href') || ''
      const response = await fetch(original, { credentials: 'same-origin' })
      if (!response.ok) return
      source = { href: original, text: await response.text() }
    }
    const background = BACKGROUND.exec(source.text)?.[1]
    const symbol = SYMBOL.exec(source.text)?.[1]
    if (!background || !symbol) return
    const svg = source.text
      .replace(`fill="${background}"`, `fill="${resolveColor('--primary')}"`)
      .replace(`stroke="${symbol}"`, `stroke="${resolveColor('--primary-foreground')}"`)
    link.type = 'image/svg+xml'
    link.href = `data:image/svg+xml,${encodeURIComponent(svg)}`
  } catch {
    // 取不到图标时保留服务器提供的原图标
  }
}

export function syncFavicon() {
  void update()
  // 主题色有过渡动画, 过渡结束后再取一次最终颜色
  watch([theme, mode], async () => {
    await nextTick()
    void update()
    setTimeout(() => void update(), cssDuration('--duration-theme') + 40)
  })
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => setTimeout(() => void update(), 80))
}
