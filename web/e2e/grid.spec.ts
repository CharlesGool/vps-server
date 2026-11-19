import { expect, open, ROUTES, setAppearance, test } from './support'
import { cardBodyProblems, cardGridProblems, structureProblems } from './layout-checks'


// 卡片栅格: 页面只有一个 CardGrid(页头加卡片), 所有控件在卡片内; 列数 1, 2, 4 按宽度选, 卡片占整数列, 高度由内容决定,
// 不重叠, 多列布局中每行排满, 同一行卡片内容量相近. 卡片内 12 栏, 块贴在栏上, 不重叠, 各行从同一组栏开始; 版式检查见 layout-checks.ts.

for (const route of ROUTES) {
  test(`页面结构 ${route}`, async ({ page }) => {
    await setAppearance(page, {})
    await open(page, route)
    expect(await structureProblems(page)).toEqual([])
  })

  test(`卡片栅格 ${route}`, async ({ page }) => {
    await setAppearance(page, {})
    await open(page, route)
    expect(await cardGridProblems(page)).toEqual([])
  })

  test(`卡片内栅格 ${route}`, async ({ page }) => {
    await setAppearance(page, {})
    await open(page, route)
    expect(await cardBodyProblems(page)).toEqual([])
  })
}

// 不同视口宽度下的列数: 每个宽度都核对列数规则(1, 2, 4 列的断点, 容器宽 472, 968 px)
for (const width of [360, 487, 488, 768, 999, 1000, 1280, 1600]) {
  test(`卡片栅格列数 ${width} px`, async ({ page }) => {
    test.skip(test.info().project.name !== 'desktop', '只在桌面项目运行')
    await page.setViewportSize({ width, height: 800 })
    await setAppearance(page, {})
    await open(page, ROUTES[0]!)
    expect(await cardGridProblems(page)).toEqual([])
    expect(await cardBodyProblems(page)).toEqual([])
  })
}
