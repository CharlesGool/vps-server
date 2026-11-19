// 卡片和块的位置属性.
// 页面卡片(PageSection, LinkCard): cols 是占的列数(1 到 4, 默认 1, 列数不足时缩到列数), rows 是跨的行数(旁边放几张矮卡片时用),
// col 是起始列(1 起, 只在 4 列布局中生效, 更窄时按顺序排列). 卡片高度由内容决定, 同一行卡片等高.
// 卡片内的块(FormField, CheckboxField, SwitchField): span 是占的栏数(1 到 12), start 是起始栏(1 到 12), rows 是跨的行数.
export interface CardLayout {
  cols?: 1 | 2 | 3 | 4
  rows?: 1 | 2 | 3 | 4
  col?: 1 | 2 | 3 | 4
}
export type Span = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12
export interface BlockLayout {
  span?: Span
  start?: Span
  rows?: 1 | 2 | 3 | 4
}

export function cardAttrs(layout: CardLayout) {
  return {
    'data-cols': layout.cols,
    'data-rows': layout.rows,
    'data-col': layout.col,
    style: { '--w': layout.cols, '--h': layout.rows, '--c': layout.col },
  }
}

export function blockAttrs(layout: BlockLayout, fallbackSpan: Span = 12) {
  const span = layout.span ?? fallbackSpan
  return {
    'data-span': span,
    'data-start': layout.start,
    'data-rows': layout.rows,
    style: { '--span': span, '--start': layout.start, '--rows': layout.rows },
  }
}
