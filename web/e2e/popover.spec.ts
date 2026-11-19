import type { Locator, Page } from '@playwright/test'
import { expect, open, setAppearance, test } from './support'

// 弹出层位置: 触发按钮贴近窗口边缘(右边, 底部)时, 弹出层必须整个留在窗口内(自动翻转或平移), 不被截断.
// 桌面和手机两个项目都运行; 手机窗口窄, 最容易暴露问题.
const POPUP = '[role="dialog"], [role="listbox"], [role="menu"], [role="tooltip"]'

async function insideViewport(page: Page, popup: Locator) {
  await expect(popup).toBeVisible()
  // 等弹出层定位完成(第一帧可能在原点)
  await page.waitForTimeout(100)
  const box = (await popup.boundingBox())!
  const { width, height } = page.viewportSize()!
  const problems: string[] = []
  if (box.x < -1) problems.push(`左边超出窗口 ${(-box.x).toFixed(0)} px`)
  if (box.y < -1) problems.push(`上边超出窗口 ${(-box.y).toFixed(0)} px`)
  if (box.x + box.width > width + 1) problems.push(`右边超出窗口 ${(box.x + box.width - width).toFixed(0)} px`)
  if (box.y + box.height > height + 1) problems.push(`下边超出窗口 ${(box.y + box.height - height).toFixed(0)} px`)
  return problems
}

// 把触发按钮滚到窗口底部, 弹出层只能向上翻转
async function toBottom(trigger: Locator) {
  await trigger.evaluate((el) => el.scrollIntoView({ block: 'end' }))
}

const CASES: { name: string; route: string; trigger: (page: Page) => Locator; bottom?: boolean }[] = [
  { name: '表格行末的操作菜单(右边缘)', route: '/showcase/data', trigger: (page) => page.getByRole('button', { name: '更多操作 host-1' }) },
  { name: '标题旁的说明(右边缘)', route: '/showcase/data', trigger: (page) => page.getByRole('button', { name: '说明' }) },
  { name: '日期日历(底部)', route: '/showcase/choices', trigger: (page) => page.getByRole('button', { name: '打开日历' }).first(), bottom: true },
  { name: '日期时间日历(右边缘)', route: '/showcase/choices', trigger: (page) => page.getByRole('button', { name: '打开日历' }).nth(1) },
  { name: '时间选择(右边缘)', route: '/showcase/choices', trigger: (page) => page.getByRole('button', { name: '选择时间' }) },
  { name: '下拉选择(底部)', route: '/showcase/choices', trigger: (page) => page.getByRole('combobox', { name: '地区' }).first(), bottom: true },
  { name: '可搜索下拉(底部)', route: '/showcase/choices', trigger: (page) => page.getByRole('combobox', { name: '可搜索的地区' }), bottom: true },
]

for (const item of CASES) {
  test(`弹出层位置 ${item.name}`, async ({ page }) => {
    await setAppearance(page, {})
    await open(page, item.route)
    const trigger = item.trigger(page)
    if (item.bottom) await toBottom(trigger)
    await trigger.click()
    expect(await insideViewport(page, page.locator(POPUP).last())).toEqual([])
  })
}
