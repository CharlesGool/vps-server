import type { ChangelogRelease } from './changelog'
import type { Locale } from './i18n'

// 模拟的变更日志: 只在开发和测试构建中、项目还没有 doc/CHANGELOG.md 时使用, 用来预览不同长度的版本卡片. 生产构建不含.
const TEXT: Record<Locale, { added: string; fixed: string; changed: string; item: (n: number) => string; long: string }> = {
  'zh-CN': { added: '新增', fixed: '修复', changed: '变更', item: (n) => `示例条目 ${n}`, long: '这是一条较长的示例说明, 用来预览多行文字在卡片里的换行和滚动效果.' },
  en: { added: 'Added', fixed: 'Fixed', changed: 'Changed', item: (n) => `Sample entry ${n}`, long: 'A longer sample entry used to preview how multi-line text wraps and scrolls inside a card.' },
  es: { added: 'Añadido', fixed: 'Corregido', changed: 'Cambiado', item: (n) => `Entrada de ejemplo ${n}`, long: 'Una entrada de ejemplo más larga para ver cómo se ajusta y desplaza el texto de varias líneas en la tarjeta.' },
}

// 每个版本的条目数(新增, 修复, 变更): 从很短到很长
const SHAPES: [string, number, number, number][] = [
  ['1.7.0 (2026-07-01)', 2, 1, 0],
  ['1.6.0 (2026-06-01)', 1, 0, 0],
  ['1.5.0 (2026-05-01)', 4, 3, 2],
  ['1.4.0 (2026-04-01)', 8, 5, 3],
  ['1.3.0 (2026-03-01)', 2, 2, 0],
  ['1.2.0 (2026-02-01)', 12, 8, 4],
  ['1.1.0 (2026-01-01)', 3, 1, 0],
  ['1.0.0 (2025-12-01)', 5, 0, 0],
]

export function sampleChangelog(locale: Locale): ChangelogRelease[] {
  const text = TEXT[locale] ?? TEXT.en
  let n = 0
  const items = (count: number) => Array.from({ length: count }, () => (++n % 3 === 0 ? `${text.item(n)}: ${text.long}` : text.item(n)))
  return SHAPES.map(([title, added, fixed, changed]) => ({
    title: `v${title}`,
    groups: [
      { title: text.added, items: items(added) },
      { title: text.fixed, items: items(fixed) },
      { title: text.changed, items: items(changed) },
    ].filter((group) => group.items.length),
  }))
}
