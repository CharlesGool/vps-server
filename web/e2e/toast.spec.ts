import type { Page } from '@playwright/test'
import { audit } from './audit'
import { expect, MODES, open, setAppearance, test, TOKENS } from './support'

// 通知: 顶部居中, 尺寸, 按类型着色, 对比度, 自动关闭时长, 悬停暂停. 测试构建(VITE_E2E=1)提供 window.__showToast.

const TONES = [
  { tone: 'success', lifetime: 4000 },
  { tone: 'destructive', lifetime: 8000 },
  { tone: 'default', lifetime: 4000 },
] as const

async function show(page: Page, tone: string) {
  await page.evaluate(
    (tone) =>
      (window as unknown as { __showToast: (t: string, tone: string, d: string) => void }).__showToast(
        '已保存',
        tone,
        '设置已更新, 刷新后仍然有效.',
      ),
    tone,
  )
  const toast = page.locator('[data-toast]')
  await expect(toast).toBeVisible()
  // 等进入动画结束再测量
  await expect(toast).not.toHaveClass(/toast-enter/)
  return toast
}

for (const mode of MODES) {
  for (const { tone } of TONES) {
    test(`通知外观 ${tone} ${mode}`, async ({ page }) => {
      await setAppearance(page, { mode })
      await open(page, '/')
      const toast = await show(page, tone)

      // 顶部居中, 宽度 min(560 px, 视口 - 32 px), 最小高度 96 px
      const box = (await toast.boundingBox())!
      // 页面始终显示纵向滚动条, 固定定位的元素以去掉滚动条后的宽度居中
      const width = await page.evaluate(() => {
        const probe = Object.assign(document.createElement('div'), { style: 'position: fixed; left: 0; right: 0' })
        document.body.append(probe)
        const value = probe.getBoundingClientRect().width
        probe.remove()
        return value
      })
      expect(Math.round(box.y)).toBe(16)
      expect(Math.abs(box.x + box.width / 2 - width / 2)).toBeLessThanOrEqual(1)
      expect(Math.round(box.width)).toBe(Math.min(560, width - 32))
      expect(box.height).toBeGreaterThanOrEqual(96)
      expect(await toast.locator('p').first().evaluate((el) => getComputedStyle(el).fontSize)).toBe('18px')
      expect((await toast.locator('svg').first().boundingBox())!.width).toBe(32)

      // 文字与背景对比度不低于 4.5
      const ratio = await toast.evaluate((el) => {
        const ctx = Object.assign(document.createElement('canvas'), { width: 1, height: 1 }).getContext('2d', {
          willReadFrequently: true,
        })!
        const rgb = (color: string) => {
          ctx.clearRect(0, 0, 1, 1)
          ctx.fillStyle = color
          ctx.fillRect(0, 0, 1, 1)
          return [...ctx.getImageData(0, 0, 1, 1).data.slice(0, 3)].map((v) => {
            const c = v / 255
            return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
          })
        }
        const lum = ([r, g, b]: number[]) => 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
        const style = getComputedStyle(el)
        const [hi, lo] = [lum(rgb(style.color)), lum(rgb(style.backgroundColor))].sort((a, b) => b - a)
        return (hi! + 0.05) / (lo! + 0.05)
      })
      expect(ratio).toBeGreaterThanOrEqual(4.5)

      expect(await page.evaluate(audit, TOKENS), '以下计算样式不在 tokens.css 中').toEqual([])
      await expect(toast).toHaveScreenshot(`toast-${tone}-${mode}.png`)

      await toast.getByRole('button', { name: '关闭' }).click()
      await expect(toast, '关闭按钮立即关闭').toHaveCount(0)
    })
  }
}

for (const { tone, lifetime } of TONES) {
  test(`通知自动关闭 ${tone}`, async ({ page }) => {
    await page.clock.install()
    await open(page, '/')
    const toast = await show(page, tone)
    await page.mouse.move(0, page.viewportSize()!.height - 1)
    await page.clock.fastForward(lifetime - 200)
    await expect(toast).toBeVisible()
    await page.clock.fastForward(400)
    await expect(toast).toHaveCount(0)
  })
}

test('悬停时暂停自动关闭', async ({ page }) => {
  test.skip(test.info().project.name === 'mobile', '触摸设备没有悬停')
  await page.clock.install()
  await open(page, '/')
  const toast = await show(page, 'success')
  await toast.hover()
  await page.clock.fastForward(20_000)
  await expect(toast).toBeVisible()
  await page.mouse.move(0, page.viewportSize()!.height - 1)
  await page.clock.fastForward(3800)
  await expect(toast).toBeVisible()
  await page.clock.fastForward(400)
  await expect(toast).toHaveCount(0)
})

test('连续触发: 替换通知时新旧通知都保持居中, 不左右跳动', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/')
  await show(page, 'success')
  // 连续触发三次, 在接下来的若干帧里记录每条可见通知的水平中心偏离窗口中心多少
  const offset = await page.evaluate(async () => {
    const trigger = (window as unknown as { __showToast: (t: string, tone: string, d: string) => void }).__showToast
    let worst = 0
    const measure = () => {
      for (const el of document.querySelectorAll('[data-toast]')) {
        const rect = el.getBoundingClientRect()
        worst = Math.max(worst, Math.abs(rect.left + rect.width / 2 - document.documentElement.clientWidth / 2))
      }
    }
    for (const tone of ['destructive', 'success', 'default']) {
      trigger('已保存', tone, '设置已更新.')
      for (let frame = 0; frame < 4; frame++) {
        await new Promise((resolve) => requestAnimationFrame(resolve))
        measure()
      }
    }
    return worst
  })
  expect(offset).toBeLessThanOrEqual(1)
})
