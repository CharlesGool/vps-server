import { ChevronsLeftRight, House, type IconNode, ScrollText, Settings } from 'lucide'
import type { RouteMeta } from 'vue-router'

const ICONS: Record<RouteMeta['icon'], IconNode> = {
  home: House,
  settings: Settings,
  changelog: ScrollText,
}

function readColor(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function renderNode(node: IconNode, stroke: string) {
  return node
    .map(([tag, attrs]) => {
      const attributes = Object.entries(attrs)
        .map(([key, value]) => `${key}="${value}"`)
        .join(' ')
      return `<${tag} ${attributes} fill="none" stroke="${stroke}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`
    })
    .join('')
}

// 统一的图标框架: 主题色圆角方块 + 页面专属的 Lucide 符号.
export function setPageIcon(icon: RouteMeta['icon'] | undefined) {
  const node = ICONS[icon ?? 'home'] ?? ChevronsLeftRight
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">` +
    `<rect width="32" height="32" rx="8" fill="${readColor('--primary')}"/>` +
    `<g transform="translate(4 4)">${renderNode(node, readColor('--primary-foreground'))}</g></svg>`
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.append(link)
  }
  link.type = 'image/svg+xml'
  link.href = `data:image/svg+xml,${encodeURIComponent(svg)}`
}
