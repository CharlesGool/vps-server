import { SHOWCASE } from '@/app.config'
import type { Locale } from './i18n'
import { sampleChangelog } from './changelog-sample'

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
  // 开发和测试构建中没有真实版本时显示模拟内容, 便于预览
  return SHOWCASE ? sampleChangelog(locale) : []
}

// 条目里的行内标记: `代码` 和 **粗体**, 其余是普通文字(不解析 HTML).
export interface InlineSegment {
  kind: 'text' | 'code' | 'strong'
  text: string
}

export function inlineSegments(item: string): InlineSegment[] {
  const segments: InlineSegment[] = []
  const pattern = /`([^`]+)`|\*\*([^*]+)\*\*/g
  let last = 0
  for (const match of item.matchAll(pattern)) {
    if (match.index > last) segments.push({ kind: 'text', text: item.slice(last, match.index) })
    segments.push(match[1] !== undefined ? { kind: 'code', text: match[1] } : { kind: 'strong', text: match[2]! })
    last = match.index + match[0].length
  }
  if (last < item.length) segments.push({ kind: 'text', text: item.slice(last) })
  return segments
}
