import { audit } from './audit'
import { expect, MODES, open, ROUTES, setAppearance, test, TOKENS } from './support'

// 运行时样式审计: 每个可见元素的计算样式都必须来自设计标记.
// 静态检查看源码写法, 这里看浏览器实际渲染的结果, 能发现组件库默认样式, 原生控件和遗漏的写法.

for (const route of ROUTES) {
  for (const mode of MODES) {
    test(`设计标记 ${route} ${mode}`, async ({ page }) => {
      await setAppearance(page, { mode })
      await open(page, route)
      const violations = await page.evaluate(audit, TOKENS)
      expect(violations, '以下计算样式不在 tokens.css 中').toEqual([])
    })
  }
}
