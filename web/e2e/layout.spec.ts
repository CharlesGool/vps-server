import { labelProblems } from './layout-checks'
import { BASE_PATH, expect, LOCALES, open, ROUTES, setAppearance, test } from './support'

// 布局: 每个路由在每种语言下检查溢出, 顶栏, 按钮文字, 选项卡下划线和选择控件.
// 语言影响文字长度, 最容易暴露换行和溢出问题.

for (const route of ROUTES) {
  for (const locale of LOCALES) {
    test(`布局 ${route} ${locale}`, async ({ page }) => {
      await setAppearance(page, { locale })
      await open(page, route)

      const problems = await page.evaluate((base) => {
        const found: string[] = []
        const describe = (el: Element) =>
          `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 24)}"`
        const visible = (el: Element) => el.checkVisibility({ visibilityProperty: true })
        const width = document.documentElement.clientWidth

        // 页面级水平滚动
        if (document.documentElement.scrollWidth > width) {
          found.push(`页面可水平滚动: scrollWidth ${document.documentElement.scrollWidth} > ${width}`)
        }

        // 元素超出视口或文字被裁切; 自身可滚动的区域(如数据表)除外
        const scrollsX = (el: Element) => /auto|scroll/.test(getComputedStyle(el).overflowX)
        for (const el of document.body.querySelectorAll('*')) {
          if (!visible(el) || el.closest('[aria-hidden="true"], .sr-only') || el.classList.contains('sr-only')) continue
          let inScroller = false
          for (let parent = el.parentElement; parent && !inScroller; parent = parent.parentElement) inScroller = scrollsX(parent)
          if (inScroller) continue
          const rect = el.getBoundingClientRect()
          if (rect.width && (rect.right > width + 1 || rect.left < -1)) found.push(`超出视口: ${describe(el)}`)
          const style = getComputedStyle(el)
          if (/hidden|clip/.test(style.overflowX) && style.textOverflow !== 'ellipsis' && el.scrollWidth > el.clientWidth + 1) {
            found.push(`内容被裁切: ${describe(el)}`)
          }
        }

        // 根元素和 body 使用相同背景
        const htmlBg = getComputedStyle(document.documentElement).backgroundColor
        const bodyBg = getComputedStyle(document.body).backgroundColor
        if (htmlBg !== bodyBg) found.push(`html 背景 ${htmlBg} 与 body 背景 ${bodyBg} 不同`)

        // 顶栏: 品牌链接指向主页; 品牌, 版本和导航项互不重叠
        const header = document.querySelector('header')
        if (!header) found.push('缺少顶栏 <header>')
        else {
          const brand = header.querySelector('a')
          if (!brand || new URL(brand.href).pathname !== base) {
            found.push('顶栏第一个链接必须是指向主页的项目名称')
          }
          const items = [...header.querySelectorAll('a')].filter(visible)
          for (let i = 0; i < items.length; i++) {
            for (let j = i + 1; j < items.length; j++) {
              const a = items[i]!.getBoundingClientRect()
              const b = items[j]!.getBoundingClientRect()
              if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) {
                found.push(`顶栏重叠: ${describe(items[i]!)} 和 ${describe(items[j]!)}`)
              }
            }
          }
          // 当前页面的导航链接标记 aria-current
          for (const link of header.querySelectorAll('nav a')) {
            const current = new URL((link as HTMLAnchorElement).href).pathname === location.pathname
            const marked = link.getAttribute('aria-current') === 'page'
            if (current !== marked) found.push(`导航 aria-current 错误: ${describe(link)}`)
          }
        }

        // 选择控件: 分段控件或单选组不超过 5 个选项
        for (const group of document.querySelectorAll('[role="radiogroup"]')) {
          const count = group.querySelectorAll('[role="radio"]').length
          if (count > 5) found.push(`单选组有 ${count} 个选项, 超过 5 个时改用列表框`)
        }
        return found
      }, BASE_PATH)
      expect([...problems, ...(await labelProblems(page))]).toEqual([])
    })
  }

  test(`选项卡下划线 ${route}`, async ({ page }) => {
    await setAppearance(page, {})
    await open(page, route)
    const lists = page.getByRole('tablist')
    for (let i = 0; i < (await lists.count()); i++) {
      const list = lists.nth(i)
      const tabs = list.getByRole('tab')
      for (let j = 0; j < (await tabs.count()); j++) {
        await tabs.nth(j).click()
        // 下划线与所选标签文字同宽同位
        const offset = await list.evaluate((el) => {
          const indicator = el.parentElement!.querySelector('[data-tab-indicator]')
          const label = el.querySelector('[aria-selected="true"] span') ?? el.querySelector('[aria-selected="true"]')
          if (!indicator || !label) return null
          const a = indicator.getBoundingClientRect()
          const b = label.getBoundingClientRect()
          return Math.max(Math.abs(a.left - b.left), Math.abs(a.width - b.width))
        })
        expect(offset, '选项卡必须使用 UnderlineTabs').not.toBeNull()
        expect(offset!).toBeLessThanOrEqual(1)
      }
    }
  })
}
