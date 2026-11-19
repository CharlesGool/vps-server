import { layoutProblems } from './layout-checks'
import { expect, MODES, open, ROUTES, setAppearance, test } from './support'

// 截图对比: 每个路由在桌面和手机宽度, 浅色和深色模式下与基准图比较; 另在平板宽度(768 px, 卡片栅格 2 列)比较浅色截图并跑全部布局检查.
// 基准图在 e2e/__screenshots__/, 随代码提交. 有意修改外观后运行 `npm run test:visual:update`,
// 逐张查看新截图确认无误后再提交.

for (const route of ROUTES) {
  for (const mode of MODES) {
    test(`截图 ${route} ${mode}`, async ({ page }) => {
      await setAppearance(page, { mode })
      await open(page, route)
      const name = route === '/' ? 'home' : route.slice(1).replaceAll('/', '-')
      await expect(page).toHaveScreenshot(`${name}-${mode}.png`, { fullPage: true })
    })
  }
}

// 平板宽度: 内容区约 720 px, 卡片栅格 2 列, 卡片内并排的字段改成上下排列; 只在桌面项目里调整窗口宽度运行
for (const route of ROUTES) {
  test(`平板截图 ${route}`, async ({ page }) => {
    test.skip(test.info().project.name !== 'desktop', '只在桌面项目运行')
    await page.setViewportSize({ width: 768, height: 1024 })
    await setAppearance(page, {})
    await open(page, route)
    expect(await layoutProblems(page)).toEqual([])
    const name = route === '/' ? 'home' : route.slice(1).replaceAll('/', '-')
    await expect(page).toHaveScreenshot(`tablet-${name}-light.png`, { fullPage: true })
  })
}
