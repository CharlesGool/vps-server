import { expect, MODES, open, setAppearance, test, THEMES } from './support'

// 主题: 八种主题色在两种模式下都可区分, 文字对比度达标, 选择刷新后保留.

// 文字和背景组合; 最低对比度按 WCAG AA: 正文 4.5, 大号文字和界面元素 3
const PAIRS: [string, string, number][] = [
  ['--foreground', '--background', 4.5],
  ['--card-foreground', '--card', 4.5],
  ['--popover-foreground', '--popover', 4.5],
  ['--muted-foreground', '--background', 4.5],
  ['--muted-foreground', '--card', 4.5],
  ['--muted-foreground', '--muted', 4.5],
  ['--primary-foreground', '--primary', 4.5],
  ['--secondary-foreground', '--secondary', 4.5],
  ['--accent-foreground', '--accent', 4.5],
  ['--destructive-foreground', '--destructive', 4.5],
  ['--success-on-surface', '--success-surface', 4.5],
  ['--destructive-on-surface', '--destructive-surface', 4.5],
  ['--primary', '--background', 3],
  ['--primary', '--card', 3],
]

// 在页面中读取标记颜色, 返回 sRGB
async function palette(page: import('@playwright/test').Page, names: string[]) {
  return page.evaluate((names) => {
    const ctx = Object.assign(document.createElement('canvas'), { width: 1, height: 1 }).getContext('2d', {
      willReadFrequently: true,
    })!
    const result: Record<string, number[]> = {}
    for (const name of names) {
      ctx.clearRect(0, 0, 1, 1)
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
      ctx.fillRect(0, 0, 1, 1)
      result[name] = [...ctx.getImageData(0, 0, 1, 1).data.slice(0, 3)]
    }
    return result
  }, names)
}

function contrast(a: number[], b: number[]) {
  const luminance = (rgb: number[]) => {
    const [r, g, bl] = rgb.map((v) => {
      const c = v / 255
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r! + 0.7152 * g! + 0.0722 * bl!
  }
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

for (const mode of MODES) {
  test(`主题色 ${mode}`, async ({ page }) => {
    const names = [...new Set(PAIRS.flat().filter((item): item is string => typeof item === 'string'))]
    const primaries = new Set<string>()
    const failures: string[] = []
    await setAppearance(page, { mode })
    await open(page, '/')
    for (const theme of THEMES) {
      await page.evaluate((theme) => (document.documentElement.dataset.theme = theme), theme)
      const colors = await palette(page, names)
      primaries.add(colors['--primary']!.join(','))
      for (const [fg, bg, min] of PAIRS) {
        const ratio = contrast(colors[fg]!, colors[bg]!)
        if (ratio < min) failures.push(`${theme}: ${fg} / ${bg} 对比度 ${ratio.toFixed(2)} < ${min}`)
      }
    }
    expect(failures).toEqual([])
    expect(primaries.size, '每种主题色的 --primary 必须不同').toBe(THEMES.length)
  })
}

test('外观选择刷新后保留', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('seeded')) {
      localStorage.clear()
      localStorage.setItem('ui.lang', 'zh-CN')
      sessionStorage.setItem('seeded', '1')
    }
  })
  await open(page, '/settings')
  const html = page.locator('html')

  await page.getByRole('radio', { name: '深色' }).click()
  await expect(html).toHaveClass(/\bdark\b/)

  // 主题色列表框必须提供全部主题色
  await page.getByRole('combobox', { name: '主题色' }).click()
  const options = page.getByRole('option')
  await expect(options).toHaveCount(THEMES.length)
  await options.nth(1).click()
  await expect(html).toHaveAttribute('data-theme', THEMES[1]!)

  await page.reload()
  await expect(html).toHaveClass(/\bdark\b/)
  await expect(html).toHaveAttribute('data-theme', THEMES[1]!)

  // 模式和主题色分别保存
  await page.getByRole('radio', { name: '浅色' }).click()
  await expect(html).not.toHaveClass(/\bdark\b/)
  await expect(html).toHaveAttribute('data-theme', THEMES[1]!)
})
