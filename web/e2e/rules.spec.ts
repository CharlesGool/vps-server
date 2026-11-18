import { expect, open, ROUTES, setAppearance, test } from './support'
import { ruleProblems } from './layout-checks'

// 尺寸, 对齐和层级: 控件高度 32, 40, 48 px, 文字行高是 8 的倍数, 触控目标, 标题层级和字号, 表单字段对齐,
// 同一行控件顶部对齐且同类型高度相同, 同一行卡片的首个块对齐, 间距刻度.
// 与 grid.spec.ts 一起构成布局的强制规范; 失败时修改页面或组件, 不修改本文件.

for (const route of ROUTES) {
  test(`尺寸和对齐 ${route}`, async ({ page }) => {
    await setAppearance(page, {})
    await open(page, route)
    expect(await ruleProblems(page)).toEqual([])
  })
}
