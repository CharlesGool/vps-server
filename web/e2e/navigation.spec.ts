import { appRoutes } from '../src/routes'
import { BASE_PATH, expect, FEATURES, open, ROUTES, setAppearance, test } from './support'

// 页面框架: 顶栏导航项, 页头路径, 仪表板入口.

const NAV = [...(FEATURES.dashboard ? ['主页'] : []), '变更日志', '设置']
const signedInRoutes = ROUTES.filter((path) => !appRoutes().find((route) => route.path === path)?.public)

for (const route of signedInRoutes) {
  test(`顶栏和页头路径 ${route}`, async ({ page }) => {
    await setAppearance(page, {})
    await open(page, route)
    const header = page.locator('header')
    // 窄屏(640 px 以下)导航收进菜单按钮
    const narrow = (page.viewportSize()?.width ?? 0) < 640
    if (narrow) {
      await expect(header.getByRole('navigation')).toBeHidden()
      await header.getByRole('button', { name: '菜单' }).click()
      await expect(page.getByRole('menu').getByRole('menuitem')).toHaveText([...NAV, ...(FEATURES.login ? ['注销'] : [])])
      await page.keyboard.press('Escape')
    } else {
      await expect(header.getByRole('navigation').getByRole('link')).toHaveText(NAV)
      await expect(header.getByRole('button', { name: '注销' })).toHaveCount(FEATURES.login ? 1 : 0)
    }
    await expect(header.getByRole('link').nth(1), '项目名称旁是版本链接').toHaveText('e2e')

    // 主页以外的页面页头有路径: 主页和上级页面是链接, 第一个链接回到主页; 主页没有路径
    const path = page.locator('main').getByRole('navigation', { name: '路径' })
    if (route === '/') await expect(path).toHaveCount(0)
    else {
      await expect(path.getByRole('link')).toHaveCount(route.split('/').filter(Boolean).length)
      await expect(path.getByRole('link').first()).toHaveAttribute('href', BASE_PATH)
    }
  })
}

test('仪表板为每个功能提供入口', async ({ page }) => {
  test.skip(!FEATURES.dashboard, '未启用仪表板')
  await open(page, '/')
  const cards = page.locator('main [data-layout="link-card"]:not([href$="/showcase"]):not([href$="/scenes"])')
  const features = appRoutes().filter((route) => !['dashboard', 'settings', 'security', 'changelog', 'login'].includes(route.view) && !route.view.startsWith('showcase'))
  await expect(cards).toHaveCount(features.length)
  await cards.first().click()
  await expect(page).toHaveURL(new RegExp(`${features[0]!.path}$`))
  await page.getByRole('navigation', { name: '路径' }).getByRole('link', { name: '仪表板' }).click()
  await expect(page).toHaveURL(/\/$/)
})

test('服务器报告的版本与显示一致', async ({ page }) => {
  const response = await page.request.get('api/session')
  test.skip(!response.headers()['content-type']?.includes('json'), '没有后端')
  const { version, login } = await response.json()
  expect(login, 'FEATURES.login 与服务器一致').toBe(FEATURES.login)
  await open(page, '/changelog')
  await expect(page.getByText(`当前版本: ${version}`)).toBeVisible()
})
