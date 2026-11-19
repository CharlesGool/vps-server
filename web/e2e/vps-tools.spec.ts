import { expect, open, test } from './support'

// vps-server 项目自己的功能页: 测速真正跑一次, 流量限制对话框保存后卡片更新.

test('浏览器测速跑完后显示四项结果', async ({ page }) => {
  test.slow()
  await open(page, '/speedtest')
  const card = page.locator('main section', { has: page.getByRole('heading', { name: '测速', exact: true }) })
  await card.getByRole('button', { name: '开始测速' }).click()
  await expect(card.getByRole('button', { name: '开始测速' })).toBeEnabled({ timeout: 30_000 })
  await expect(card.getByText('完成')).toHaveCount(4)
  await expect(card.getByText(/^\s*\d+\.\d+\s*Mbps\s*$/)).toHaveCount(2)
})

test('流量限制保存后卡片显示新上限, 错误的值不保存', async ({ page }) => {
  await open(page, '/speedtest')
  const card = page.locator('main section', { has: page.getByRole('heading', { name: '流量', exact: true }) })
  await card.getByRole('button', { name: '流量限制' }).click()
  const dialog = page.getByRole('dialog', { name: '流量限制' })
  await dialog.getByLabel('流量上限（GiB）').fill('-1')
  await dialog.getByRole('button', { name: '保存限制' }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  await dialog.getByLabel('流量上限（GiB）').fill('5')
  await dialog.getByRole('button', { name: '保存限制' }).click()
  await expect(dialog).toBeHidden()
  await expect(card.getByText(/^5 GiB/)).toBeVisible()
  // 恢复不限, 不影响其他测试和截图
  await card.getByRole('button', { name: '流量限制' }).click()
  await dialog.getByLabel('流量上限（GiB）').fill('')
  await dialog.getByRole('button', { name: '保存限制' }).click()
  await expect(dialog).toBeHidden()
  await expect(card.getByText('不限', { exact: true })).toBeVisible()
})

test('iperf3: 端口默认遮住, 显示后是数字; 关闭了窗口功能时开启给出提示', async ({ page }) => {
  await open(page, '/iperf')
  const server = page.locator('main section', { has: page.getByRole('heading', { name: '服务端', exact: true }) })
  const port = server.locator('dd').nth(1)
  await expect(port.locator('code')).toHaveText('••••••')
  await port.getByRole('button', { name: '显示 端口' }).click()
  await expect(port.locator('code')).toHaveText(/^\d+$/)
  await expect(port.getByRole('button', { name: '隐藏 端口' })).toHaveAttribute('aria-pressed', 'true')
  // 测试服务器设置了 VPSSRV_IPERF_ENABLE=0
  await server.getByRole('button', { name: '开启服务' }).click()
  await expect(page.getByText('此次安装关闭了 iperf3 窗口', { exact: false }).last()).toBeVisible()
  // 不可用的端口
  await server.getByRole('button', { name: '修改端口' }).click()
  const dialog = page.getByRole('dialog', { name: '修改端口' })
  await dialog.getByLabel('端口').fill('80')
  await dialog.getByRole('button', { name: '保存端口' }).click()
  await expect(page.getByText('端口不可用，或测试窗口正在运行。')).toBeVisible()
})
