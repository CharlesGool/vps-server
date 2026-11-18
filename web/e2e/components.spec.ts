import { audit } from './audit'
import { cardBodyProblems } from './layout-checks'
import { expect, MODES, open, setAppearance, test, TOKENS } from './support'

// 组件样例页中弹出层和交互: 日期选择, 时间输入, 列表框, 复选框, 开关, 对话框.
// 弹出层打开后同样做设计标记审计和截图对比.

for (const mode of MODES) {
  test(`日期选择弹出层 ${mode}`, async ({ page }) => {
    await setAppearance(page, { mode })
    await open(page, '/showcase/choices')
    await page.getByRole('button', { name: '打开日历' }).first().click()
    const calendar = page.getByRole('dialog')
    await expect(calendar.getByRole('application')).toBeVisible()
    await expect(calendar.locator('[aria-label^="日期, "]'), '日历标签使用字段名').toHaveCount(1)
    expect(await page.evaluate(audit, TOKENS), '弹出层计算样式').toEqual([])
    await expect(calendar).toHaveScreenshot(`showcase-calendar-${mode}.png`)
    await calendar.getByRole('button', { name: /5月20日/ }).click()
    await expect(calendar).toBeHidden()
    await expect(page.getByRole('group', { name: '日期', exact: true }).first()).toContainText('20')

    // 日历顶部直接选年份和月份
    await page.getByRole('button', { name: '打开日历' }).first().click()
    await page.getByRole('dialog').getByRole('combobox', { name: '年份' }).click()
    await page.getByRole('option', { name: '2020' }).click()
    await page.getByRole('dialog').getByRole('combobox', { name: '月份' }).click()
    await page.getByRole('option', { name: '三月' }).click()
    await page.getByRole('dialog').getByRole('button', { name: /2020年3月15日/ }).click()
    await expect(page.getByRole('group', { name: '日期', exact: true }).first()).toContainText('2020')
  })

  test(`时间选择弹出层 ${mode}`, async ({ page }) => {
    await setAppearance(page, { mode })
    await open(page, '/showcase/choices')
    await page.getByRole('button', { name: '选择时间' }).click()
    const popover = page.getByRole('dialog', { name: '时间' })
    await expect(popover.getByRole('listbox', { name: '时' })).toBeVisible()
    expect(await page.evaluate(audit, TOKENS), '时间弹出层计算样式').toEqual([])
    await expect(popover).toHaveScreenshot(`showcase-time-${mode}.png`)
    await popover.getByRole('listbox', { name: '时' }).getByRole('option', { name: '14' }).click()
    await popover.getByRole('listbox', { name: '分' }).getByRole('option', { name: '45' }).click()
    await popover.getByRole('button', { name: '确定' }).click()
    await expect(popover).toBeHidden()
    const time = page.getByRole('group', { name: '时间', exact: true }).first()
    await expect(time).toContainText('14')
    await expect(time).toContainText('45')
  })

  test(`列表框 ${mode}`, async ({ page }) => {
    await setAppearance(page, { mode })
    await open(page, '/showcase/choices')
    await page.getByRole('combobox', { name: '地区', exact: true }).click()
    const listbox = page.getByRole('listbox')
    await expect(listbox.getByRole('option')).toHaveCount(6)
    expect(await page.evaluate(audit, TOKENS), '列表框计算样式').toEqual([])
    await expect(listbox).toHaveScreenshot(`showcase-select-${mode}.png`)
    await listbox.getByRole('option', { name: '华东' }).click()
    await expect(page.getByRole('combobox', { name: '地区', exact: true })).toHaveText('华东')
  })

  test(`对话框 ${mode}`, async ({ page }) => {
    await setAppearance(page, { mode })
    await open(page, '/showcase/overlays')
    await page.getByRole('button', { name: '添加' }).click()
    const dialog = page.getByRole('dialog', { name: '添加项目' })
    await expect(dialog).toBeVisible()
    expect(await page.evaluate(audit, TOKENS), '对话框计算样式').toEqual([])
    expect(await cardBodyProblems(page), '对话框内栅格').toEqual([])
    await expect(page).toHaveScreenshot(`showcase-dialog-${mode}.png`)
    await dialog.getByRole('button', { name: '关闭' }).click()
    await expect(dialog).toBeHidden()
  })
}

test('复选框, 开关和时间输入', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/showcase/choices')
  const agree = page.getByRole('checkbox', { name: /使用条款/ })
  await expect(agree).toBeChecked()
  await agree.click()
  await expect(agree).not.toBeChecked()
  const notify = page.getByRole('switch', { name: '接收通知' })
  await expect(notify).not.toBeChecked()
  await page.getByText('接收通知').click()
  await expect(notify).toBeChecked()
  // 时间为 24 小时制, 没有上午/下午分段
  const time = page.getByRole('group', { name: '时间', exact: true }).first()
  await expect(time).toContainText('09')
  await expect(time.getByRole('spinbutton')).toHaveCount(2)
})
