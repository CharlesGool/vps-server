// 从设计标记读取时长, 让脚本动画与 tokens.css 使用同一来源.
export function cssDuration(name: string): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  const value = Number.parseFloat(raw)
  if (Number.isNaN(value)) return 0
  return raw.endsWith('ms') ? value : value * 1000
}

export function reducedMotion(): boolean {
  return matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function easeOutCubic(t: number): number {
  return 1 - (1 - t) ** 3
}
