import { audit } from './audit'
import { layoutProblems } from './layout-checks'
import { expect, open, setAppearance, test, TOKENS } from './support'

// 控件行为: 分页, 表格排序和多选, 确认对话框, 提示条. 外观和布局由 grid.spec.ts, rules.spec.ts, tokens.spec.ts 检查.

test('分页, 排序和多选', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/data')
  const table = page.getByRole('table', { name: '数据表' })
  await expect(table.getByRole('row')).toHaveCount(6)
  await expect(page.getByText('1-5 条, 共 12 条')).toBeVisible()

  await page.getByRole('button', { name: '第 2 页' }).click()
  await expect(page.getByText('6-10 条, 共 12 条')).toBeVisible()
  await expect(table.getByRole('cell', { name: 'host-6', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '上一页' }).click()

  // 排序: 升序, 降序, 取消
  const sort = page.getByRole('button', { name: '按 请求数 排序' })
  await sort.click()
  await expect(table.getByRole('columnheader', { name: /请求数/ })).toHaveAttribute('aria-sort', 'ascending')
  const first = async () => (await table.getByRole('row').nth(1).getByRole("cell").nth(3).innerText()).trim()
  const ascending = Number(await first())
  await sort.click()
  await expect(table.getByRole('columnheader', { name: /请求数/ })).toHaveAttribute('aria-sort', 'descending')
  expect(Number(await first())).toBeGreaterThanOrEqual(ascending)
  await sort.click()
  await expect(table.getByRole('columnheader', { name: /请求数/ })).toHaveAttribute('aria-sort', 'none')

  // 多选: 单选一行, 再全选, 再取消
  await table.getByRole('checkbox', { name: '选择 1' }).click()
  await expect(page.getByRole('status').filter({ hasText: '已选 1 项' })).toBeVisible()
  await table.getByRole('checkbox', { name: '全选' }).click()
  await expect(page.getByRole('status').filter({ hasText: '已选 5 项' })).toBeVisible()
  await table.getByRole('checkbox', { name: '全选' }).click()
  await expect(page.getByRole('status').filter({ hasText: '已选' })).toHaveCount(0)
})

test('确认对话框: 取消不执行, 确认才执行', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/feedback')
  await page.getByRole('button', { name: '删除', exact: true }).click()
  const dialog = page.getByRole('alertdialog', { name: '删除这个项目?' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '取消' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByText('已删除.')).toHaveCount(0)

  await page.getByRole('button', { name: '删除', exact: true }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('已删除.')).toBeVisible()
})

test('提示条的角色', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/feedback')
  await expect(page.locator('[data-alert][data-tone="destructive"]')).toHaveAttribute('role', 'alert')
  await expect(page.locator('[data-alert][data-tone="warning"]').first()).toHaveAttribute('role', 'alert')
  await expect(page.locator('[data-alert][data-tone="info"]')).toHaveAttribute('role', 'status')
})

test('操作菜单: 危险项要再确认', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/overlays')
  await page.getByRole('button', { name: '更多操作' }).click()
  await page.getByRole('menuitem', { name: '删除' }).click()
  const dialog = page.getByRole('alertdialog', { name: '删除这个项目?' })
  await expect(dialog).toBeVisible()
  await expect(page.getByText('已删除.')).toHaveCount(0)
  await dialog.getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('已删除.')).toBeVisible()
})

test('单选, 可搜索下拉, 多选, 标签和数字', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/choices')
  // 单选组
  await page.getByRole('radio', { name: '手动同步' }).click()
  await expect(page.getByRole('radio', { name: '手动同步' })).toBeChecked()
  await expect(page.getByRole('radio', { name: '自动同步' })).not.toBeChecked()
  // 可搜索下拉: 输入筛选
  const combo = page.getByRole('combobox', { name: '可搜索的地区' })
  await combo.fill('东')
  await expect(page.getByRole('option')).toHaveCount(1)
  await page.getByRole('option', { name: '华东' }).click()
  await expect(combo).toHaveValue('华东')
  await combo.fill('不存在')
  await expect(page.getByText('无匹配项')).toBeVisible()
  await combo.press('Escape')
  // 多选
  const multi = page.getByRole('combobox', { name: '多选地区' })
  await expect(page.getByText('已选 2 项')).toBeVisible()
  await multi.click()
  await page.getByRole('option', { name: '西部' }).click()
  await expect(page.getByText('已选 3 项')).toBeVisible()
  await page.keyboard.press('Escape')
  // 标签
  const tags = page.getByPlaceholder('输入后按回车')
  await tags.fill('gamma')
  await tags.press('Enter')
  await expect(page.getByRole('button', { name: '移除 gamma' })).toBeVisible()
  await page.getByRole('button', { name: '移除 alpha' }).click()
  await expect(page.getByRole('button', { name: '移除 alpha' })).toHaveCount(0)
  // 数字
  const number = page.getByRole('spinbutton', { name: '超时时间' })
  await expect(number).toHaveValue('30')
  await page.getByRole('button', { name: '增加' }).click()
  await expect(number).toHaveValue('35')
  await page.getByRole('button', { name: '减少' }).click()
  await page.getByRole('button', { name: '减少' }).click()
  await expect(number).toHaveValue('25')
})

test('文件上传: 校验类型和大小, 可移除', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/inputs')
  await expect(page.getByText('report.pdf')).toBeVisible()
  await page.getByRole('button', { name: '移除 report.pdf' }).click()
  await expect(page.getByText('report.pdf')).toHaveCount(0)
  const input = page.locator('input[type="file"]')
  await input.setInputFiles([
    { name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('x') },
    { name: 'big.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(6 * 1048576) },
    { name: 'ok.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(1024) },
  ])
  await expect(page.getByRole('alert').filter({ hasText: 'notes.txt' })).toContainText('文件类型不支持')
  await expect(page.getByRole('alert').filter({ hasText: 'big.pdf' })).toContainText('超过')
  await expect(page.getByText('ok.pdf')).toBeVisible()
})

test('编辑页: 未保存的修改离开前要确认', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/scenes/edit')
  const save = page.getByRole('button', { name: '保存' })
  await expect(save).toBeDisabled()
  // 没有修改可以直接离开: 路径中的"场景样例"链接
  await page.getByRole('navigation', { name: '路径' }).getByRole('link', { name: '场景样例' }).click()
  await expect(page).toHaveURL(/\/scenes$/)
  await page.goBack()

  await page.getByLabel('名称').fill('host-2')
  await expect(page.getByRole('alert').filter({ hasText: '有未保存的修改.' })).toBeVisible()
  await expect(save).toBeEnabled()
  // 离开: 取消留在当前页, 放弃才离开
  await page.getByRole('navigation', { name: '路径' }).getByRole('link', { name: '场景样例' }).click()
  const dialog = page.getByRole('alertdialog', { name: '放弃未保存的修改?' })
  await expect(dialog).toBeVisible()
  expect(await page.evaluate(audit, TOKENS), '确认对话框计算样式').toEqual([])
  await dialog.getByRole('button', { name: '取消' }).click()
  await expect(page).toHaveURL(/\/scenes\/edit$/)
  // 校验: 名称必填
  await page.getByLabel('名称').fill('')
  await save.click()
  await expect(page.getByText('必填.')).toBeVisible()
  // 保存后可以直接离开
  await page.getByLabel('名称').fill('host-3')
  await save.click()
  await expect(page.getByText('已保存.')).toBeVisible()
  await page.getByRole('navigation', { name: '路径' }).getByRole('link', { name: '场景样例' }).click()
  await expect(page).toHaveURL(/\/scenes$/)
})

test('多步向导: 每步校验, 每步布局', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/scenes/wizard')
  const next = page.getByRole('button', { name: '下一步' })
  await expect(page.getByRole('button', { name: '上一步' })).toBeDisabled()
  await expect(page.getByRole('listitem').filter({ hasText: '基本信息' })).toHaveAttribute('aria-current', 'step')
  await next.click()
  await expect(page.getByText('必填.')).toBeVisible()
  await page.getByLabel('名称').fill('demo')
  expect(await layoutProblems(page), '第 1 步布局').toEqual([])
  await next.click()
  await expect(page.getByRole('listitem').filter({ hasText: '同步设置' })).toHaveAttribute('aria-current', 'step')
  await page.getByRole('radio', { name: '手动同步' }).click()
  expect(await layoutProblems(page), '第 2 步布局').toEqual([])
  await next.click()
  await expect(page.getByText('手动同步')).toBeVisible()
  expect(await layoutProblems(page), '第 3 步布局').toEqual([])
  await page.getByRole('button', { name: '上一步' }).click()
  await expect(page.getByRole('radio', { name: '手动同步' })).toBeChecked()
  await next.click()
  await page.getByRole('button', { name: '完成' }).click()
  await expect(page.getByText('已完成创建.')).toBeVisible()
})

test('弹出层的计算样式: 可搜索下拉, 操作菜单, 确认对话框', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/choices')
  await page.getByRole('combobox', { name: '可搜索的地区' }).click()
  await expect(page.getByRole('option').first()).toBeVisible()
  expect(await page.evaluate(audit, TOKENS), '可搜索下拉').toEqual([])
  await page.keyboard.press('Escape')
  await open(page, '/showcase/overlays')
  await page.getByRole('button', { name: '更多操作' }).click()
  await expect(page.getByRole('menuitem').first()).toBeVisible()
  expect(await page.evaluate(audit, TOKENS), '操作菜单').toEqual([])
  await page.keyboard.press('Escape')
  await open(page, '/showcase/feedback')
  await page.getByRole('button', { name: '删除', exact: true }).click()
  expect(await page.evaluate(audit, TOKENS), '确认对话框').toEqual([])
})

test('仪表板的数据卡', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/scenes/dashboard')
  const cards = page.locator('[data-layout="stat-card"]')
  await expect(cards).toHaveCount(4)
  // 涨跌的好坏: 错误率下降是好事(绿色), 平均延迟上升是坏事(红色)
  await expect(cards.nth(2).locator('[data-badge]')).toHaveClass(/text-success-on-surface/)
  await expect(cards.nth(3).locator('[data-badge]')).toHaveClass(/text-destructive-on-surface/)
})

test('详情页: 描述列表和操作', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/scenes/detail')
  await expect(page.getByRole('term').first()).toBeVisible()
  await page.getByRole('link', { name: '编辑' }).click()
  await expect(page).toHaveURL(/\/scenes\/edit$/)
})

test('折叠面板: 一次展开一项, 键盘可操作', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/layout')
  const first = page.getByRole('button', { name: '卡片栅格是什么?' })
  const second = page.getByRole('button', { name: '一张卡片可以占几列?' })
  await expect(first).toHaveAttribute('aria-expanded', 'true')
  await second.click()
  await expect(second).toHaveAttribute('aria-expanded', 'true')
  await expect(first).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByText('用 cols 指定 1 到 4 列')).toBeVisible()
  await second.focus()
  await page.keyboard.press('Enter')
  await expect(second).toHaveAttribute('aria-expanded', 'false')
  expect(await layoutProblems(page)).toEqual([])
})

test('树形列表: 展开, 收起, 键盘移动和选中', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/data')
  const tree = page.getByRole('tree', { name: '项目文件' })
  await expect(tree.getByRole('treeitem', { name: 'main.ts' })).toBeVisible()
  const cmd = tree.getByRole('treeitem', { name: 'cmd' })
  await expect(cmd).toHaveAttribute('aria-expanded', 'false')
  await cmd.click()
  await expect(cmd).toHaveAttribute('aria-expanded', 'true')
  await expect(tree.getByRole('treeitem', { name: 'server' })).toBeVisible()
  await tree.getByRole('treeitem', { name: 'App.vue' }).click()
  await expect(tree.getByRole('treeitem', { name: 'App.vue' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText('已选中 App.vue')).toBeVisible()
  // 方向键移到下一项, 回车选中
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(tree.getByRole('treeitem', { name: 'router.ts' })).toHaveAttribute('aria-selected', 'true')
  expect(await layoutProblems(page)).toEqual([])
})

test('头像: 没有图片时显示名字缩写, 名字在旁边', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/data')
  const table = page.getByRole('table', { name: '成员' })
  await expect(table.getByRole('cell', { name: 'Ada Lovelace' })).toBeVisible()
  await expect(table.locator('[data-avatar]').first()).toContainText('AL')
  await expect(table.locator('[data-avatar]').nth(1)).toContainText('明')
})

test('侧边抽屉: 打开, 布局, 关闭后焦点回到按钮', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/overlays')
  const trigger = page.getByRole('button', { name: '查看详情' })
  await trigger.click()
  const drawer = page.getByRole('dialog', { name: '主机详情' })
  await expect(drawer).toBeVisible()
  // 贴在窗口右侧, 高度占满
  const box = (await drawer.boundingBox())!
  const viewport = page.viewportSize()!
  expect(Math.abs(box.x + box.width - viewport.width)).toBeLessThanOrEqual(1)
  expect(box.height).toBeCloseTo(viewport.height, 0)
  expect(await layoutProblems(page)).toEqual([])
  expect(await page.evaluate(audit, TOKENS), '抽屉').toEqual([])
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('复制按钮: 复制后提示, 图标变成对勾', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await setAppearance(page, {})
  await open(page, '/showcase/inputs')
  await page.getByRole('button', { name: '复制' }).first().click()
  await expect(page.getByText('已复制').first()).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('https://api.example.com/v1')
  await open(page, '/scenes/detail')
  await page.getByRole('button', { name: '复制 地址' }).click()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('192.168.1.20')
})

test('图表: 每个数据点一个图形, 读屏有数据表, 悬停显示数值', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/charts')
  const charts = page.locator('[data-chart]')
  await expect(charts).toHaveCount(3)
  await expect(charts.nth(0).locator('[data-chart-mark]')).toHaveCount(24)
  await expect(charts.nth(1).locator('[data-chart-mark]')).toHaveCount(3)
  await expect(charts.nth(2).locator('[data-chart-mark]')).toHaveCount(8)
  // 只给读屏的数据表: 每组数据一行
  await expect(page.getByRole('table', { name: '各季度资源使用率' }).getByRole('row')).toHaveCount(3)
  // 图形在绘图区内, 柱子不超出纵轴顶端
  const svg = (await charts.nth(2).locator('svg').boundingBox())!
  for (const bar of await charts.nth(2).locator('[data-chart-mark]').all()) {
    const rect = (await bar.boundingBox())!
    expect(rect.y).toBeGreaterThanOrEqual(svg.y)
    expect(rect.x + rect.width).toBeLessThanOrEqual(svg.x + svg.width)
  }
  // 悬停(手机上是点按): 提示框显示这一项的数值, 不超出卡片
  await charts.nth(2).locator('svg rect[fill="transparent"]').last().hover()
  const tip = charts.nth(2).locator('[data-chart-tip]')
  await expect(tip).toContainText('Q4')
  await expect(tip).toContainText('86%')
  const card = (await charts.nth(2).locator('xpath=ancestor::*[@data-card][1]').boundingBox())!
  const tipBox = (await tip.boundingBox())!
  expect(tipBox.x).toBeGreaterThanOrEqual(card.x)
  expect(tipBox.x + tipBox.width).toBeLessThanOrEqual(card.x + card.width)
  expect(await layoutProblems(page)).toEqual([])
})

test('搜索结果: 筛选, 标出匹配, 没有结果时显示空状态', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/scenes/search')
  const search = page.getByRole('searchbox', { name: '搜索' })
  await expect(page.getByText('共 11 条结果')).toBeVisible()
  await expect(page.locator('[data-result-list] mark').first()).toHaveText('host')
  await page.getByRole('radio', { name: '文档' }).click()
  await expect(page.getByText('共 2 条结果')).toBeVisible()
  await expect(page.locator('[data-pagination]')).toHaveCount(0)
  await search.fill('不存在的内容')
  await expect(page.getByText('没有找到结果')).toBeVisible()
  await expect(page.locator('[data-result-list]')).toHaveCount(0)
  expect(await layoutProblems(page)).toEqual([])
  await search.fill('备份')
  await expect(page.getByRole('link', { name: '备份和恢复' })).toBeVisible()
})
