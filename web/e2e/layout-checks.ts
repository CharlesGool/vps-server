import type { Page } from '@playwright/test'
import { DESIGN } from './support'

// 布局检查: 卡片栅格, 卡片内栅格, 版式, 尺寸和对齐. 视觉测试的每个路由都运行它们; 需要先操作才出现的状态(如已验证的安全设置, 打开的对话框)在测试中另行调用.
// 规则(见 webui-behavior.md 的 `栅格和尺寸`):
// 1. 页面只有一个 CardGrid: 页头(不是卡片)加卡片, 所有控件都在卡片(或页头)里.
// 2. 列数 1, 2, 4 按容器宽度选(没有 3 列): 列宽不小于 --card-min-width, 列间距 --space-card; 卡片占整数列, 高度由内容决定, 不重叠, 多列布局中除最后一行外每行排满.
// 3. 卡片内 12 栏, 间距 --space-field, 内边距 --space-card; 块的左右边缘贴在栏上, 不重叠, 同一行排满 12 栏, 各行的块从同一组栏开始.
// 4. 版式: 同一行卡片的内容高度相近(填充率), 一张卡片不只放一个小控件, 卡片标题不和卡片里的字段或设置项标签重复, 每张卡片最多一个主按钮且在按钮行最后,
//    按钮宽度随文字(有上下限), 数据表超过 10 行必须分页.
// 5. 纵向: 控件高度 32, 40, 48 px, 文字行高是 8 的倍数; 同一行的控件顶部对齐, 同类型同大小控件高度相同.

export function structureProblems(page: Page): Promise<string[]> {
  return page.evaluate(({ content, radius }) => {
    const found: string[] = []
    const visible = (el: Element) => el.checkVisibility({ visibilityProperty: true })
    const describe = (el: Element) => `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 24)}"`
    const main = document.querySelector('main')!

    const top = [...main.children].filter(visible)
    if (top.length !== 1 || (top[0] as HTMLElement).dataset.layout !== 'card-grid') {
      found.push(`内容区必须只有一个 CardGrid, 发现 ${top.map(describe).join(', ') || '空'}`)
      return found
    }
    const grid = top[0]!
    // 页面不能横向滚动(常见原因: 隐藏元素或表格把页面撑宽)
    const root = document.documentElement
    if (root.scrollWidth > root.clientWidth + 1) found.push(`页面横向溢出: 内容宽 ${root.scrollWidth} px, 窗口宽 ${root.clientWidth} px`)
    if (grid.getBoundingClientRect().width > content + 1) found.push(`内容区宽度 ${grid.getBoundingClientRect().width} px, 最大 ${content} px`)

    // CardGrid 的子元素: 页头(只能是第一个), 卡片, 或包着卡片的 CardForm
    const cells = grid.querySelector('[data-card-cells]')!
    const cards: Element[] = []
    ;[...cells.children].forEach((child, index) => {
      const el = child as HTMLElement
      // CardForm 是 display: contents, 没有自己的盒子, 不参与可见性判断
      if (!el.matches('[data-form-scope]') && !visible(child)) return
      if (el.matches('[data-layout="page-header"]')) {
        if (index !== 0) found.push('页头必须是 CardGrid 的第一个子元素')
      } else if (el.matches('[data-card]')) cards.push(el)
      else if (el.matches('[data-form-scope]')) {
        for (const inner of el.children) {
          if (!visible(inner)) continue
          if (inner.matches('[data-card]')) cards.push(inner)
          else found.push(`CardForm 里只能放卡片, 发现 ${describe(inner)}`)
        }
      } else found.push(`CardGrid 里只能放 PageHeader, 卡片(PageSection, LinkCard, StatCard)或 CardForm, 发现 ${describe(el)}`)
    })
    if (!cards.length) found.push('页面没有卡片')
    for (const card of main.querySelectorAll('[data-card] [data-card]')) found.push(`卡片不能嵌套: ${describe(card)}`)
    for (const card of cards) {
      const value = Number.parseFloat(getComputedStyle(card).borderTopLeftRadius)
      if (value !== radius) found.push(`卡片圆角 ${value} px, 应为 ${radius} px: ${describe(card)}`)
    }

    // 页面上的每个控件都在卡片里; 页头只有路径链接和设置按钮
    const interactive = main.querySelectorAll('a[href], button, input, textarea, select, [role="checkbox"], [role="switch"], [role="radio"], [role="tab"], [role="combobox"], [role="slider"], [data-control]')
    for (const control of interactive) {
      if (!visible(control) || (control as HTMLInputElement).type === 'hidden') continue
      if (!control.closest('[data-card-body], [data-layout="page-header"]')) found.push(`控件不在卡片内: ${describe(control)}`)
    }
    return found
  }, { content: DESIGN.content, radius: DESIGN.cardRadius })
}

export function cardGridProblems(page: Page): Promise<string[]> {
  return page.evaluate((design) => {
    const found: string[] = []
    const allowed = [1, 2, 4]
    const visible = (el: Element) => el.checkVisibility({ visibilityProperty: true })
    const describe = (el: Element) => `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 24)}"`
    const px = (value: string) => (value === 'normal' ? 0 : Number.parseFloat(value))
    const cells = document.querySelector('[data-card-cells]')
    if (!cells) return ['缺少 CardGrid']
    const style = getComputedStyle(cells)
    const tracks = style.gridTemplateColumns.split(' ').map(Number.parseFloat)
    const gridRect = cells.getBoundingClientRect()
    const columns = tracks.length
    const gap = px(style.columnGap)

    // 列数: 列宽不小于最小宽度, 不超过最大列数, 只取 1, 2, 4; 列间距和行间距都是 --space-card
    if (!allowed.includes(columns)) found.push(`列数 ${columns}, 只能是 ${allowed.join(', ')}`)
    const fit = Math.max(1, Math.min(design.maxColumns, Math.floor((gridRect.width + design.spaceCard + 0.5) / (design.minCardWidth + design.spaceCard))))
    const expected = [...allowed].reverse().find((value) => value <= fit)!
    if (columns !== expected) found.push(`宽度 ${gridRect.width.toFixed(0)} px 应有 ${expected} 列, 实际 ${columns} 列`)
    if (gap !== design.spaceCard || px(style.rowGap) !== design.spaceCard) found.push(`卡片间距应为 ${design.spaceCard} px, 实际 ${style.columnGap} / ${style.rowGap}`)

    // 页头占满一行
    const header = cells.querySelector(':scope > [data-layout="page-header"]')
    if (header && Math.abs(header.getBoundingClientRect().width - gridRect.width) > 1) found.push('页头必须占满一行')

    // 卡片占整数列, 与声明一致
    const pitch = tracks[0]! + gap
    const rowTops = [...new Set([...cells.querySelectorAll('[data-card]')].filter(visible).map((card) => Math.round(card.getBoundingClientRect().top)))].sort((a, b) => a - b)
    const placed: { card: Element; col: number; span: number; row: number; rowEnd: number }[] = []
    let explicit = false
    for (const card of [...cells.querySelectorAll('[data-card]')].filter(visible)) {
      const rect = card.getBoundingClientRect()
      const col = (rect.left - gridRect.left) / pitch
      const span = (rect.width + gap) / pitch
      if (Math.abs(col - Math.round(col)) * pitch > 1 || Math.abs(span - Math.round(span)) * pitch > 1) {
        found.push(`卡片没有占整数列: 第 ${col.toFixed(2)} 列起占 ${span.toFixed(2)} 列: ${describe(card)}`)
        continue
      }
      const want = Math.min(Number(card.getAttribute('data-cols') ?? 1), columns)
      if (Math.round(span) !== want) found.push(`卡片应占 ${want} 列, 实际 ${Math.round(span)} 列: ${describe(card)}`)
      if (card.hasAttribute('data-col')) {
        explicit = true
        if (columns === design.maxColumns && Math.round(col) + 1 !== Number(card.getAttribute('data-col'))) found.push(`卡片应从第 ${card.getAttribute('data-col')} 列开始, 实际第 ${Math.round(col) + 1} 列: ${describe(card)}`)
      }
      if (Math.round(col) + Math.round(span) > columns) found.push(`卡片超出栅格: ${describe(card)}`)
      if (card.scrollWidth > card.clientWidth + 1) found.push(`卡片内容横向溢出: ${describe(card)}`)
      const row = rowTops.findIndex((top) => Math.abs(top - rect.top) <= 1)
      const rowEnd = rowTops.filter((top) => top < rect.bottom - 1).length
      placed.push({ card, col: Math.round(col), span: Math.round(span), row, rowEnd })
    }
    // 卡片不能重叠
    for (let i = 0; i < placed.length; i++) {
      for (let j = i + 1; j < placed.length; j++) {
        const a = placed[i]!.card.getBoundingClientRect()
        const b = placed[j]!.card.getBoundingClientRect()
        if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1) found.push(`卡片重叠: ${describe(placed[i]!.card)} 和 ${describe(placed[j]!.card)}`)
      }
    }
    // 多列布局中, 除最后一行外每行都要排满; 显式指定起始列(col)时不检查
    if (columns > 1 && !explicit && rowTops.length > 1) {
      for (let row = 0; row < rowTops.length - 1; row++) {
        const used = placed.filter((item) => item.row <= row && item.rowEnd > row).reduce((sum, item) => sum + item.span, 0)
        if (used < columns) found.push(`第 ${row + 1} 行只排了 ${used} 列, 共 ${columns} 列: 调整卡片的 cols 或顺序, 使每行排满`)
      }
    }
    // 填充率: 同一行卡片等高, 内容只占卡片高度很少一部分说明这一行的卡片搭配不当
    for (const { card } of placed) {
      const body = card as HTMLElement
      const blocks = [...body.children].filter(visible)
      if (!blocks.length) continue
      const rect = body.getBoundingClientRect()
      const bottom = Math.max(...blocks.map((block) => block.getBoundingClientRect().bottom)) + px(getComputedStyle(body).paddingBottom)
      const fill = (bottom - rect.top) / rect.height
      if (fill < 0.6) found.push(`卡片内容只占高度的 ${Math.round(fill * 100)}%, 同一行卡片的内容量差太多: ${describe(card)}`)
    }
    return found
  }, DESIGN)
}

// 所有可见的卡片内栅格(页面卡片和对话框)
export function cardBodyProblems(page: Page): Promise<string[]> {
  return page.evaluate((design) => {
    const found: string[] = []
    const visible = (el: Element) => el.checkVisibility({ visibilityProperty: true })
    const describe = (el: Element) => `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 24)}"`
    const px = (value: string) => (value === 'normal' ? 0 : Number.parseFloat(value))
    const near = (a: number, b: number, tolerance = 1) => Math.abs(a - b) <= tolerance
    const text = (el: Element | null | undefined) => (el?.textContent ?? '').trim()

    for (const body of document.querySelectorAll('[data-card-body]')) {
      if (!visible(body)) continue
      const style = getComputedStyle(body)
      const tracks = style.gridTemplateColumns.split(' ').map(Number.parseFloat)
      if (tracks.length !== design.cardColumns) found.push(`卡片内栅格 ${tracks.length} 栏, 应为 ${design.cardColumns} 栏: ${describe(body)}`)
      if (px(style.columnGap) !== design.spaceField || px(style.rowGap) !== design.spaceField) found.push(`卡片内块之间的间距应为 ${design.spaceField} px: ${describe(body)}`)
      if (['Top', 'Right', 'Bottom', 'Left'].some((side) => px(style.getPropertyValue(`padding-${side.toLowerCase()}`)) !== design.spaceCard)) found.push(`卡片内边距应为 ${design.spaceCard} px: ${describe(body)}`)

      // 栏线: 每一栏的左右边缘
      const rect = body.getBoundingClientRect()
      const gap = px(style.columnGap)
      let x = rect.left + body.clientLeft + px(style.paddingLeft)
      const starts: number[] = []
      const ends: number[] = []
      for (const width of tracks) {
        starts.push(x)
        ends.push(x + width)
        x += width + gap
      }
      const blocks = [...body.children].filter(visible)
      const placed: { block: Element; start: number; span: number; top: number; bottom: number }[] = []
      let explicit = false
      let rowSpans = false
      for (const block of blocks) {
        const blockRect = block.getBoundingClientRect()
        const start = starts.findIndex((line) => near(line, blockRect.left))
        const end = ends.findIndex((line) => near(line, blockRect.right))
        if (start < 0 || end < 0) {
          found.push(`块的左右边缘没有贴在栏上: ${describe(block)}`)
          continue
        }
        placed.push({ block, start, span: end - start + 1, top: blockRect.top, bottom: blockRect.bottom })
        if (block.hasAttribute('data-start')) {
          explicit = true
          if (start + 1 !== Number(block.getAttribute('data-start'))) found.push(`块应从第 ${block.getAttribute('data-start')} 栏开始, 实际第 ${start + 1} 栏: ${describe(block)}`)
        }
        if (Number(block.getAttribute('data-rows') ?? 1) > 1) rowSpans = true
      }
      for (let i = 0; i < placed.length; i++) {
        for (let j = i + 1; j < placed.length; j++) {
          const a = placed[i]!
          const b = placed[j]!
          if (a.start < b.start + b.span && b.start < a.start + a.span && a.top < b.bottom - 1 && b.top < a.bottom - 1) found.push(`块重叠: ${describe(a.block)} 和 ${describe(b.block)}`)
        }
      }
      // 同一行排满 12 栏, 各行的块从同一组栏开始(以块最多的一行为准); 指定 start 或有跨行的块时不检查
      if (!explicit && !rowSpans) {
        const rows: { top: number; items: typeof placed }[] = []
        for (const item of placed) {
          const row = rows.find((candidate) => near(candidate.top, item.top))
          if (row) row.items.push(item)
          else rows.push({ top: item.top, items: [item] })
        }
        for (const row of rows) {
          const total = row.items.reduce((sum, item) => sum + item.span, 0)
          if (total !== design.cardColumns) {
            found.push(`同一行的栏数之和为 ${total}, 应为 ${design.cardColumns}(或用 start 指定位置): ${describe(row.items[0]!.block)}`)
          }
        }
        const widest = rows.reduce((best, row) => (row.items.length > best.items.length ? row : best), rows[0] ?? { top: 0, items: [] })
        const lines = new Set(widest.items.map((item) => item.start))
        for (const row of rows) {
          for (const item of row.items) {
            if (!lines.has(item.start)) found.push(`块从第 ${item.start + 1} 栏开始, 和其他行的列(第 ${[...lines].map((line) => line + 1).join(', ')} 栏)对不齐: ${describe(item.block)}`)
          }
        }
      }

      // 字段必须直接放在卡片中
      for (const field of body.querySelectorAll('[data-form-field]')) {
        if (visible(field) && field.parentElement !== body) found.push(`FormField 必须直接放在 PageSection 或 AppDialog 中: ${describe(field)}`)
      }

      // 版式: 卡片标题和卡片里某个字段或设置项的标签相同(同一个词出现两次)
      const title = body.querySelector(':scope > [data-card-title]')
      const labels = [...body.querySelectorAll(':scope > [data-form-field] > label, :scope > [data-form-field] > span, :scope > [data-row-style] [data-row-label]')].filter((label) => visible(label) && !label.classList.contains('sr-only'))
      const same = labels.find((label) => text(label) === text(title))
      if (title && same) found.push(`卡片标题和字段标签重复("${text(title)}"): 改卡片标题(写模块名), 只有一个字段时也可以用 hide-label`)

      // 版式: 一张卡片只放一个小控件
      if (body.matches('[data-card]:not([data-layout="link-card"])')) {
        const content = blocks.filter((block) => !block.matches('[data-card-title], [data-card-description]'))
        const single = content[0]?.matches('[data-form-actions]') ? content[0].children.length === 1 : content[0]?.matches('[data-form-field], [data-control]')
        if (content.length === 1 && single && content[0]!.getBoundingClientRect().height < 80) {
          found.push(`一张卡片只放了一个小控件: 把同一类设置合进一张卡片(模块): ${describe(body)}`)
        }
      }

      // 数据表一次最多显示 10 行, 更多的数据用 PaginationBar 分页
      // vps-server(项目决策 2026-11-20): 标了 data-table-long 的长列表(进程, 服务, 端口, 文件, 集中管理)一页最多 50 行
      for (const table of body.querySelectorAll('table')) {
        const count = table.querySelectorAll('tbody tr').length
        const limit = table.closest('[data-table-long]') ? 50 : 10
        if (visible(table) && count > limit) found.push(`数据表一次显示了 ${count} 行, 最多 ${limit} 行, 更多的数据用 PaginationBar 分页: ${describe(body)}`)
      }

      // 同一张卡片只用一种样式: 表单样式(标签在上的字段, 勾选框)和设置行样式(左边名称右边控件的设置项, 开关)不混用
      const formStyle = body.querySelector(':scope > [data-form-field], :scope > [data-form-style]')
      const rowStyle = body.querySelector(':scope > [data-row-style]')
      if (formStyle && rowStyle && visible(formStyle) && visible(rowStyle)) found.push(`同一张卡片混用了表单样式(${describe(formStyle)})和设置行样式(${describe(rowStyle)}): 拆成两张卡片, 或统一成一种`)

      // 勾选框和开关与标签第一行上下居中
      for (const choice of body.querySelectorAll('[data-choice]')) {
        if (!visible(choice)) continue
        const control = choice.querySelector('[data-choice-control]')!.getBoundingClientRect()
        const label = choice.querySelector('[data-choice-label]')!
        const line = Number.parseFloat(getComputedStyle(label).lineHeight)
        const labelTop = label.getBoundingClientRect().top
        if (!near(control.top + control.height / 2, labelTop + line / 2)) found.push(`勾选框或开关没有和标签第一行上下居中: ${describe(choice)}`)
      }

      // 主按钮: 每张卡片最多一个; 按钮行靠右时放最后
      const primaries = [...body.querySelectorAll('[data-slot="button"][data-variant="default"]')].filter((button) => visible(button) && button.closest('[data-card-body]') === body)
      if (primaries.length > 1) found.push(`一张卡片有 ${primaries.length} 个主按钮, 最多一个: ${describe(body)}`)
      for (const actions of body.querySelectorAll(':scope > [data-form-actions]:not([data-align="start"]):not([data-block])')) {
        const buttons = [...actions.querySelectorAll('[data-slot="button"]')].filter(visible)
        const primary = buttons.findIndex((button) => button.getAttribute('data-variant') === 'default')
        if (primary >= 0 && primary !== buttons.length - 1) found.push(`靠右的按钮行里主按钮必须在最后: ${describe(actions)}`)
      }
    }
    return found
  }, DESIGN)
}

export function ruleProblems(page: Page): Promise<string[]> {
  return page.evaluate((design) => {
    const found: string[] = []
    const visible = (el: Element) => el.checkVisibility({ visibilityProperty: true })
    const describe = (el: Element) => `<${el.tagName.toLowerCase()}> "${(el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 24)}"`
    const near = (a: number, b: number, tolerance = 1) => Math.abs(a - b) <= tolerance

    // 控件高度只有 3 档
    const controls = [...document.querySelectorAll('[data-slot="button"], [data-slot="input"], [data-control="field"]')].filter(visible)
    for (const control of controls) {
      const height = control.getBoundingClientRect().height
      if (!design.controlHeights.some((allowed) => near(height, allowed))) {
        found.push(`控件高度 ${height} px, 只能是 ${design.controlHeights.join(', ')} px: ${describe(control)}`)
      }
    }

    // 文字行高是行单位(8 px)的倍数
    for (const el of document.body.querySelectorAll('*')) {
      if (!visible(el) || el.closest('[aria-hidden="true"], [data-grid-overlay]')) continue
      if (![...el.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent!.trim())) continue
      const lineHeight = Number.parseFloat(getComputedStyle(el).lineHeight)
      if (Number.isNaN(lineHeight) || !near(lineHeight % design.rowUnit, 0, 0.01)) found.push(`行高 ${getComputedStyle(el).lineHeight}, 必须是 ${design.rowUnit} px 的倍数: ${describe(el)}`)
    }

    // 触控目标: 交互元素的宽和高都不小于最小值; 行内链接除外
    const targets = [...document.querySelectorAll('a[href], button, [role="checkbox"], [role="switch"], [role="radio"], [role="tab"], [role="combobox"], [role="slider"], input')].filter(visible)
    for (const target of targets) {
      if (target.closest('[aria-hidden="true"]') || (target as HTMLInputElement).type === 'hidden') continue
      if (target.tagName === 'A' && getComputedStyle(target).display === 'inline') continue
      const rect = target.getBoundingClientRect()
      if (Math.min(rect.width, rect.height) < design.touchMin - 0.5) {
        found.push(`触控目标 ${rect.width.toFixed(0)}×${rect.height.toFixed(0)} px, 不小于 ${design.touchMin} px: ${describe(target)}`)
      }
    }

    // 标题: 恰有一个 h1, 层级不跳级; 字号 h1 24, h2 18
    const headings = [...document.querySelectorAll('main h1, main h2, main h3, main h4, main h5, main h6')].filter(visible)
    const levels = headings.map((heading) => Number(heading.tagName[1]))
    if (levels.filter((level) => level === 1).length !== 1) found.push(`每页必须有且只有一个 h1, 实际 ${levels.filter((level) => level === 1).length} 个`)
    levels.forEach((level, index) => {
      if (index > 0 && level > levels[index - 1]! + 1) found.push(`标题层级跳级: h${levels[index - 1]} 后面是 h${level}`)
    })
    const SIZE = { 1: 24, 2: 18, 3: 14 } as Record<number, number>
    headings.forEach((heading, index) => {
      const size = Number.parseFloat(getComputedStyle(heading).fontSize)
      const expected = SIZE[levels[index]!]
      if (expected && size !== expected) found.push(`h${levels[index]} 字号 ${size} px, 应为 ${expected} px: ${describe(heading)}`)
    })

    // 多行输入框高度只有两档
    for (const area of document.querySelectorAll('[data-control="area"]')) {
      if (!visible(area)) continue
      const height = area.getBoundingClientRect().height
      if (!design.areaHeights.some((allowed) => near(height, allowed))) found.push(`多行输入框高度 ${height} px, 只能是 ${design.areaHeights.join(', ')} px`)
    }

    // 表单字段: 标签与控件左对齐; 非组字段的控件填满字段宽度
    for (const field of [...document.querySelectorAll('[data-form-field]')].filter(visible)) {
      const [label, control] = [field.children[0], field.children[1]]
      if (!label || !control || field.hasAttribute('data-label-hidden')) continue
      if (!near(label.getBoundingClientRect().left, control.getBoundingClientRect().left)) found.push(`标签与控件没有左对齐: ${describe(field)}`)
      if (!field.hasAttribute('data-form-field-group') && !near(control.getBoundingClientRect().right, field.getBoundingClientRect().right)) {
        found.push(`控件没有填满字段宽度: ${describe(field)}`)
      }
    }

    // 对齐: 同一行的块顶部对齐, 同一行同类型的控件高度相同, 同一行字段的控件顶部对齐
    for (const body of document.querySelectorAll('[data-card-body]')) {
      if (!visible(body)) continue
      const blocks: Element[] = []
      for (const child of body.children) {
        if (!visible(child)) continue
        if (child.matches('[data-form-actions]')) blocks.push(...[...child.children].filter(visible))
        else blocks.push(child)
      }
      const rows: Element[][] = []
      for (const block of blocks) {
        const row = rows.find((candidate) => near(candidate[0]!.getBoundingClientRect().top, block.getBoundingClientRect().top, 1))
        if (row) row.push(block)
        else rows.push([block])
      }
      for (const row of rows) {
        if (row.length < 2) continue
        const key = (el: Element) => (el.matches('[data-form-field]') ? 'field' : (el.getAttribute('data-slot') ?? el.tagName))
        const fields = row.filter((el) => el.matches('[data-form-field]'))
        const innerTops = fields.map((field) => field.children[1]?.getBoundingClientRect().top).filter((top): top is number => top !== undefined)
        if (innerTops.some((top) => !near(top, innerTops[0]!))) found.push('同一行表单字段的控件顶部没有对齐(同一行不要混用隐藏标签和有标签的字段)')
        for (const el of row) {
          const peer = row.find((other) => key(other) === key(el))!
          if (!near(el.getBoundingClientRect().height, peer.getBoundingClientRect().height) && key(el) !== 'field') found.push(`同一行同类型控件高度不同: ${describe(el)}`)
        }
      }
    }

    // 同一行卡片: 每张卡片第一个块距卡片上沿的距离相同, 所以标题和首个控件在同一水平线上
    const cards = [...document.querySelectorAll('[data-card]')].filter(visible)
    const byRow = new Map<number, Element[]>()
    for (const card of cards) {
      const key = Math.round(card.getBoundingClientRect().top)
      byRow.set(key, [...(byRow.get(key) ?? []), card])
    }
    for (const row of byRow.values()) {
      const first = (card: Element) => {
        const child = [...card.children].find(visible)
        return child?.matches('[data-form-actions]') ? [...child.children].find(visible) : child
      }
      const firsts = row.map((card) => (first(card)?.getBoundingClientRect().top ?? 0) + card.scrollTop).filter((top): top is number => top !== undefined)
      if (firsts.some((top) => !near(top, firsts[0]!))) found.push(`同一行卡片的第一个块没有对齐: ${row.map((card) => describe(card)).join(' | ')}`)
    }

    // 按钮宽度随文字: 按钮行里的文字按钮不窄于 --button-min-width, 不宽于 --button-max-width(登录卡等 block 按钮行除外)
    for (const button of document.querySelectorAll('[data-form-actions]:not([data-block]) > [data-slot="button"]')) {
      if (!visible(button)) continue
      const width = button.getBoundingClientRect().width
      if (width < design.buttonMin - 1 || width > design.buttonMax + 1) found.push(`按钮宽 ${width.toFixed(0)} px, 应在 ${design.buttonMin} 到 ${design.buttonMax} px 之间: ${describe(button)}`)
    }
    // 按钮必须看得出边界: 有底色或边框; 没有边框也没有底色的文字按钮不允许
    for (const button of document.querySelectorAll('[data-slot="button"]')) {
      if (!visible(button)) continue
      const style = getComputedStyle(button)
      const transparent = (color: string) => color === 'transparent' || /rgba\(.*,\s*0\)$/.test(color) || /\/\s*0\)$/.test(color)
      if (transparent(style.backgroundColor) && Number.parseFloat(style.borderTopWidth) === 0) found.push(`按钮看不出边界(没有底色也没有边框): ${describe(button)}`)
    }

    // 间距刻度: 每个可见元素的内边距和间隙只取刻度值
    const allowed = new Set([...design.spacing, 1])
    for (const el of document.body.querySelectorAll('*')) {
      if (!visible(el) || el.closest('[aria-hidden="true"], [data-grid-overlay]')) continue
      const style = getComputedStyle(el)
      for (const property of ['padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'row-gap', 'column-gap']) {
        const raw = style.getPropertyValue(property)
        if (raw === 'normal' || raw === '') continue
        const value = Number.parseFloat(raw)
        if (!allowed.has(Math.round(value))) found.push(`${property} ${value} px 不在间距刻度内: ${describe(el)}`)
      }
    }
    return found
  }, DESIGN)
}

// 按钮和链接文字不能被截断或溢出; 每种语言都检查, 因为译文长度不同
export function labelProblems(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const found: string[] = []
    for (const el of document.querySelectorAll('main [data-slot="button"], main [data-slot="button"] *')) {
      if (!el.checkVisibility({ visibilityProperty: true })) continue
      if (el.scrollWidth > el.clientWidth + 1) found.push(`文字被截断或溢出: "${(el.textContent ?? '').trim().slice(0, 24)}"`)
    }
    return found
  })
}

// 所有布局检查; 需要先操作才出现的状态在测试中调用
export async function layoutProblems(page: Page): Promise<string[]> {
  return [
    ...(await structureProblems(page)),
    ...(await cardGridProblems(page)),
    ...(await cardBodyProblems(page)),
    ...(await ruleProblems(page)),
    ...(await labelProblems(page)),
  ]
}
