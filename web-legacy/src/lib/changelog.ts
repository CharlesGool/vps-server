import type { Locale } from './i18n'

// 应用内变更日志取自项目的 doc/CHANGELOG.md 和 doc/<lang>/CHANGELOG.md.
const files = import.meta.glob<string>('../../../doc/**/CHANGELOG.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const PATHS: Record<Locale, string> = {
  'zh-CN': '../../../doc/CHANGELOG.md',
  en: '../../../doc/en/CHANGELOG.md',
  es: '../../../doc/es/CHANGELOG.md',
}

export interface ChangelogRelease {
  title: string
  groups: { title: string; items: string[] }[]
}

// 版本为 `### `, 分类为 `#### `, 条目为 `- `.
function parse(markdown: string): ChangelogRelease[] {
  const releases: ChangelogRelease[] = []
  for (const line of markdown.split('\n')) {
    if (line.startsWith('### ')) releases.push({ title: line.slice(4).trim(), groups: [] })
    else if (line.startsWith('#### ')) releases.at(-1)?.groups.push({ title: line.slice(5).trim(), items: [] })
    else if (line.startsWith('- ')) releases.at(-1)?.groups.at(-1)?.items.push(line.slice(2).trim())
  }
  return releases
}

// 缺失翻译时回退到英文, 再回退到简体中文.
export function loadChangelog(locale: Locale): ChangelogRelease[] {
  for (const candidate of [locale, 'en', 'zh-CN'] as const) {
    const releases = parse(files[PATHS[candidate]] ?? '')
    if (releases.length) return releases
  }
  return []
}
