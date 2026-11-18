import type { TOKENS } from './support'

// 运行时样式审计: 每个可见元素的计算样式都必须来自设计标记. 在页面中运行, 不能引用外部变量.
type Tokens = typeof TOKENS

export function audit(tokens: Tokens): string[] {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 1
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!

  // 任意 CSS 颜色转为 sRGB 0-255 和不透明度
  function rgba(color: string): [number, number, number, number] {
    ctx.clearRect(0, 0, 1, 1)
    ctx.fillStyle = '#000'
    ctx.fillStyle = color
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
    return [r!, g!, b!, a! / 255]
  }

  // 用探针元素让浏览器解析标记, 结果与页面元素的计算值格式一致
  const probe = document.createElement('div')
  probe.style.position = 'absolute'
  probe.style.visibility = 'hidden'
  document.body.append(probe)
  const resolve = (property: string, value: string) => {
    probe.style.setProperty(property, value)
    const computed = getComputedStyle(probe).getPropertyValue(property)
    probe.style.removeProperty(property)
    return computed
  }

  const palette = tokens.colors.map(({ name, value }) => ({ name, rgba: rgba(resolve('color', value)) }))
  const fonts = new Set(tokens.fonts.map((value) => resolve('font-family', value)))
  // 阴影规范化为 "颜色 RGBA + 尺寸"; 去掉 Tailwind ring 等完全透明的占位阴影.
  // 颜色写法因构建工具不同而不同, 所以比较解析后的 RGBA.
  const splitShadow = (value: string) =>
    value === 'none'
      ? ''
      : value
          .split(/,(?![^(]*\))/)
          .map((part) => {
            const color = part.match(/[a-z-]+\([^)]*\)|#[0-9a-f]+|transparent/i)?.[0] ?? 'black'
            const [r, g, b, a] = rgba(color)
            if (a === 0) return ''
            const size = part.replace(color, '').trim().replace(/\s+/g, ' ')
            return `${r} ${g} ${b} ${a.toFixed(2)} ${size}`
          })
          .filter(Boolean)
          .join(', ')
  const shadows = new Set(['', ...tokens.shadows.map((value) => splitShadow(resolve('box-shadow', value)))])
  probe.remove()

  const near = (a: number, b: number, tolerance = 0.5) => Math.abs(a - b) <= tolerance
  const isSpacing = (value: number) => near(value / tokens.spacing, Math.round(value / tokens.spacing), 0.01)
  const isRadius = (value: number) => value === 0 || value >= 9999 || tokens.radii.some((radius) => near(radius, value))

  function colorName(color: string): string | null | undefined {
    const [r, g, b, a] = rgba(color)
    // 完全透明或很淡的叠加色(如 bg-primary/10)不检查, 颜色名已由静态检查限制
    if (a < 0.25) return null
    const match = palette.find(({ rgba: [pr, pg, pb] }) => near(r, pr, 3) && near(g, pg, 3) && near(b, pb, 3))
    return match?.name
  }

  function describe(el: Element): string {
    const id = el.id ? `#${el.id}` : ''
    const classes = typeof el.className === 'string' && el.className ? `.${el.className.trim().split(/\s+/).slice(0, 4).join('.')}` : ''
    const text = (el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 24)
    return `<${el.tagName.toLowerCase()}${id}${classes}>${text ? ` "${text}"` : ''}`
  }

  const found = new Set<string>()
  const report = (el: Element, message: string) => found.add(`${describe(el)} ${message}`)

  for (const el of document.body.querySelectorAll('*')) {
    if (!(el instanceof HTMLElement) || ['SCRIPT', 'STYLE', 'TEMPLATE'].includes(el.tagName)) continue
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue
    const style = getComputedStyle(el)
    const hasText = [...el.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent!.trim())

    if (hasText) {
      const size = Number.parseFloat(style.fontSize)
      if (!tokens.textSizes.some((token) => near(token, size))) report(el, `字号 ${style.fontSize}`)
      if (!tokens.weights.includes(Number(style.fontWeight))) report(el, `字重 ${style.fontWeight}`)
      if (!fonts.has(style.fontFamily)) report(el, `字体 ${style.fontFamily}`)
      if (colorName(style.color) === undefined) report(el, `文字颜色 ${style.color}`)
    }

    // 主题色样本自带 data-theme, 显示的是其他主题的颜色
    if (!el.hasAttribute('data-theme') && colorName(style.backgroundColor) === undefined) {
      report(el, `背景色 ${style.backgroundColor}`)
    }
    for (const side of ['top', 'right', 'bottom', 'left']) {
      if (Number.parseFloat(style.getPropertyValue(`border-${side}-width`)) === 0) continue
      const color = style.getPropertyValue(`border-${side}-color`)
      if (colorName(color) === undefined) report(el, `边框色 ${color}`)
    }

    for (const corner of ['top-left', 'top-right', 'bottom-right', 'bottom-left']) {
      const value = style.getPropertyValue(`border-${corner}-radius`)
      if (value.includes('%') || !isRadius(Number.parseFloat(value))) report(el, `圆角 ${value}`)
    }

    for (const side of ['top', 'right', 'bottom', 'left']) {
      const value = style.getPropertyValue(`padding-${side}`)
      if (!isSpacing(Number.parseFloat(value))) report(el, `内边距 ${value}`)
    }
    for (const property of ['row-gap', 'column-gap']) {
      const value = style.getPropertyValue(property)
      if (value !== 'normal' && !isSpacing(Number.parseFloat(value))) report(el, `间隙 ${value}`)
    }

    if (!shadows.has(splitShadow(style.boxShadow))) report(el, `阴影 ${style.boxShadow}`)
  }
  return [...found]
}
