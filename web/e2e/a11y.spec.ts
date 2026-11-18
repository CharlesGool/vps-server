import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { expect, MODES, open, ROUTES, setAppearance, test } from './support'

// 无障碍扫描(axe-core, WCAG 2.2 A 和 AA): 每个路由的浅色和深色都扫描, 另外扫描需要先操作才出现的弹出层.
// 规则来自 axe-core 自身, 不在这里放宽; 确实不适用的规则在 DISABLED 中写明理由.
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']
const DISABLED: string[] = []

async function scan(page: Page, include?: string) {
  const builder = new AxeBuilder({ page }).withTags(TAGS).disableRules(DISABLED)
  if (include) builder.include(include)
  const result = await builder.analyze()
  return result.violations.map((violation) => `${violation.id}: ${violation.help} -> ${violation.nodes.map((node) => node.target.join(' ')).join(', ')}`)
}

for (const route of ROUTES) {
  for (const mode of MODES) {
    test(`无障碍 ${route} ${mode}`, async ({ page }) => {
      await setAppearance(page, { mode })
      await open(page, route)
      expect(await scan(page)).toEqual([])
    })
  }
}

// 弹出层: 打开后只扫描弹出层本身. 下拉框和菜单打开时 reka 用 aria-hidden 隐藏页面其余部分并把焦点锁在弹出层里(模态),
// axe 只认 aria-modal 对话框这种模态写法, 会把被隐藏的页面报成"隐藏的元素可聚焦"; 页面其余部分已在上面关闭弹出层时扫描过.
const POPUP = '[role="dialog"], [role="alertdialog"], [role="listbox"], [role="menu"]'
const POPUPS: { name: string; route: string; open: (page: Page) => Promise<unknown> }[] = [
  { name: '下拉选择', route: '/showcase/choices', open: (page) => page.getByRole('combobox', { name: '地区' }).first().click() },
  { name: '可搜索下拉', route: '/showcase/choices', open: (page) => page.getByRole('combobox', { name: '可搜索的地区' }).click() },
  { name: '日历', route: '/showcase/choices', open: (page) => page.getByRole('button', { name: '打开日历' }).first().click() },
  { name: '操作菜单', route: '/showcase/overlays', open: (page) => page.getByRole('button', { name: '更多操作' }).click() },
  { name: '对话框', route: '/showcase/overlays', open: (page) => page.getByRole('button', { name: '添加', exact: true }).click() },
  { name: '侧边抽屉', route: '/showcase/overlays', open: (page) => page.getByRole('button', { name: '查看详情' }).click() },
  { name: '确认对话框', route: '/showcase/feedback', open: (page) => page.getByRole('button', { name: '删除', exact: true }).click() },
]
for (const popup of POPUPS) {
  for (const mode of MODES) {
    test(`无障碍 弹出层 ${popup.name} ${mode}`, async ({ page }) => {
      await setAppearance(page, { mode })
      await open(page, popup.route)
      await popup.open(page)
      await expect(page.locator(POPUP).first()).toBeVisible()
      expect(await scan(page, POPUP)).toEqual([])
    })
  }
}
