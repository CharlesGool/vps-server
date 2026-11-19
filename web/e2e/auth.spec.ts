import { layoutProblems } from './layout-checks'
import { E2E_PASSWORD, expect, FEATURES, open, setAppearance, signIn, test } from './support'

// 登录和访问: 只在 FEATURES.login 为 true 时运行. 测试服务器信任 127.0.0.1 的 X-Forwarded-For,
// 每个测试用不同的局域网地址, 互不影响失败次数和白名单.

test.skip(!FEATURES.login, '未启用登录')

// 桌面和手机两组测试并行运行, 共用一个服务器; 每组用不同的客户端地址
const clientIP = (host: number) => `192.168.${test.info().project.name === 'mobile' ? 201 : 200}.${host}`

// 注销: 窄屏(640 px 以下)导航在菜单按钮里
async function signOut(page: import('@playwright/test').Page) {
  if ((page.viewportSize()?.width ?? 0) < 640) {
    await page.locator('header').getByRole('button', { name: '菜单' }).click()
    await page.getByRole('menuitem', { name: '注销' }).click()
  } else await page.getByRole('button', { name: '注销' }).click()
}

const box = async (locator: import('@playwright/test').Locator) => (await locator.boundingBox())!

test('登录页布局', async ({ page }) => {
  await setAppearance(page, {})
  await open(page, '/login')
  const header = page.locator('header')
  expect((await box(header)).height, '顶栏最小高度 72 px').toBeGreaterThanOrEqual(72)
  // 项目决策 2026-10-07: 顶栏只显示项目名称, 不显示项目标志
  await expect(header.locator('a').first().locator('span, svg'), '顶栏没有项目标志').toHaveCount(0)
  await expect(header.getByRole('navigation'), '登录页顶栏只有项目名称').toHaveCount(0)

  // 登录页同样是卡片栅格: 所有控件在卡片内, 高度 48 px
  for (const control of [
    page.getByLabel('密码', { exact: true }),
    page.getByRole('button', { name: '登录', exact: true }),
    page.getByRole('button', { name: 'IP 免密访问' }),
  ]) {
    expect((await box(control)).height, '表单控件高度 48 px').toBe(48)
    await expect(page.locator('main [data-card]').filter({ has: control })).toHaveCount(1)
  }
  await expect(page.locator('main [data-card]').filter({ has: page.getByRole('link', { name: /e2e/ }) }), '版本链接在卡片内').toHaveCount(1)
  await expect(page.locator('main [data-card]').filter({ has: page.getByRole('radiogroup', { name: '语言' }) }), '语言选择在卡片内').toHaveCount(1)
})

test('密码显示切换不改变值和焦点', async ({ page }) => {
  await open(page, '/login')
  const input = page.getByLabel('密码', { exact: true })
  await input.fill('secret-value')
  await page.getByRole('button', { name: '显示' }).click()
  await expect(input).toHaveAttribute('type', 'text')
  await expect(input).toHaveValue('secret-value')
  await expect(input).toBeFocused()
  await expect(page).toHaveURL(/\/login/)
  await page.getByRole('button', { name: '隐藏' }).press('Enter')
  await expect(input).toHaveAttribute('type', 'password')
})

test('密码登录, 跳回原页面, 注销', async ({ page }) => {
  await page.setExtraHTTPHeaders({ 'X-Forwarded-For': clientIP(1) })
  await open(page, '/settings', { signedIn: false })
  await expect(page).toHaveURL(/\/login\?redirect=/)

  await page.getByLabel('密码', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveText('密码错误.')

  await page.getByLabel('密码', { exact: true }).fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/settings$/)

  await signOut(page)
  await expect(page).toHaveURL(/\/login/)
  await page.goto('./')
  await expect(page, '注销后会话已结束').toHaveURL(/\/login/)
})

test('安全设置和无密码 IP 访问', async ({ page, context }) => {
  const ip = clientIP(2)
  await page.setExtraHTTPHeaders({ 'X-Forwarded-For': ip })
  await setAppearance(page, {})

  // 未加入白名单: 停留在登录页并提示
  await open(page, '/login')
  await page.getByRole('button', { name: 'IP 免密访问' }).click()
  await expect(page.getByRole('status').filter({ hasText: '设置 → 安全' })).toBeVisible()
  await expect(page).toHaveURL(/\/login/)

  // 普通设置的"安全"只是入口; 进入安全设置需要管理员验证
  await open(page, '/settings')
  await page.getByRole('link', { name: '进入安全设置' }).click()
  await expect(page).toHaveURL(/\/settings\/security$/)
  if ((page.viewportSize()?.width ?? 0) < 640) {
    await page.locator('header').getByRole('button', { name: '菜单' }).click()
    await expect(page.getByRole('menuitem', { name: '设置' })).toHaveAttribute('aria-current', 'location')
    await page.keyboard.press('Escape')
  } else await expect(page.locator('header').getByRole('link', { name: '设置' })).toHaveAttribute('aria-current', 'location')
  // vps-server: 密码登录本身算一次管理员验证(10 分钟内有效), 所以刚登录时直接进入, 不再要求验证
  const verify = page.getByLabel('管理员密码')
  if (await verify.isVisible()) {
    await verify.fill(E2E_PASSWORD)
    await page.getByRole('button', { name: '验证' }).click()
  }

  const address = page.getByLabel('IP 地址')
  const add = page.getByRole('button', { name: '添加' })
  await address.fill('8.8.8.8')
  await add.click()
  await expect(page.getByRole('alert')).toHaveText('只接受私有网段内的单个地址.')
  await address.fill(ip)
  await add.click()
  // vps-server 的安全页同时显示安全记录(含刚添加的地址), 所以只在白名单表格里找
  await expect(page.getByRole('table', { name: '允许的地址' }).getByText(ip, { exact: true })).toBeVisible()
  await address.fill(ip)
  await add.click()
  await expect(page.getByRole('alert')).toHaveText('地址已在白名单中.')
  await address.fill('')
  await page.getByRole('switch', { name: '启用 IP 免密访问' }).click()
  await expect(page.getByRole('switch', { name: '启用 IP 免密访问' })).toBeChecked()
  expect(await layoutProblems(page), '安全设置(已验证)的布局').toEqual([])
  await page.locator('#app').evaluate(() => document.fonts.ready)
  await expect(page).toHaveScreenshot('security-ready.png', { fullPage: true })

  // 注销清除 IP 访问记录
  await signOut(page)
  await expect(page).toHaveURL(/\/login/)
  expect(await page.evaluate(() => localStorage.getItem('auth.ipAccess'))).toBeNull()

  // vps-server 的 IP 免密登录只认连接本身的地址, 从不信任 X-Forwarded-For; 测试连接来自 127.0.0.1(不在私有网段白名单内),
  // 所以这里只能验证被拒绝时停留在登录页. IP 登录成功和仅 IP 会话不能进入安全设置由 tests/test_spa_api.py 覆盖;
  // 有记录时自动发起 IP 访问(前端 session.ts, 来自模板)在这里测不到.
  await page.getByRole('button', { name: 'IP 免密访问' }).click()
  await expect(page.getByRole('status').filter({ hasText: '设置 → 安全' })).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
  void context
})

test('显示的版本与服务器一致', async ({ page }) => {
  await signIn(page)
  const response = await page.request.get('api/session')
  const { version } = await response.json()
  await open(page, '/settings')
  await expect(page.locator('header').getByRole('link', { name: `版本 ${version}` })).toHaveText(version)
})
