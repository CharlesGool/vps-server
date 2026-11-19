#!/usr/bin/env node
// 设计检查: 拒绝绕过设计标记的写法. 只有 src/styles/tokens.css 可以写具体数值.
// 页面(src/components/ 以外的 .vue)另检查结构: 禁止原生控件, 自己排列, 外边距, 自写栅格和卡片表面, 内边距只用固定几档.
// 允许值从 tokens.css 读取, 新增标记后无需修改本脚本.
// 用法: node scripts/check-design.mjs; 发现问题时退出码为 1.
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(root, 'src')
const tokensPath = join(src, 'styles', 'tokens.css')
const IGNORE = 'design-check-ignore'

// ---- 从 tokens.css 收集允许的标记 ----
const tokensCss = readFileSync(tokensPath, 'utf8')
function names(prefix) {
  const found = new Set()
  for (const match of tokensCss.matchAll(new RegExp(`--${prefix}-([a-z0-9-]+?)\\s*:`, 'g'))) {
    if (!match[1].includes('--') && match[1] !== '*') found.add(match[1])
  }
  return found
}
const colors = names('color')
const textSizes = new Set([...names('text')].filter((name) => !name.includes('-')))
const radii = names('radius')
const shadows = names('shadow')
const weights = names('font-weight')
const families = new Set([...names('font')].filter((name) => !name.startsWith('weight')))
const containers = names('container')
const eases = names('ease')
const leadings = names('leading')

// ---- 工具类规则 ----
const set = (text) => new Set(text.split(' '))
const TEXT_KEYWORDS = set('left center right justify start end wrap nowrap balance pretty ellipsis clip')
const BG_KEYWORDS = set(
  'none fixed local scroll auto cover contain center top bottom left right left-top left-bottom right-top right-bottom repeat no-repeat repeat-x repeat-y repeat-round repeat-space clip-border clip-padding clip-content clip-text origin-border origin-padding origin-content blend-normal',
)
const BORDER_KEYWORDS = set('solid dashed dotted double hidden none collapse separate')
const OUTLINE_KEYWORDS = set('none hidden solid dashed dotted double')
const DECORATION_KEYWORDS = set('solid double dotted dashed wavy auto from-font clone slice')
const RADIUS_SIDES = /^(?:(t|r|b|l|s|e|tl|tr|br|bl|ss|se|es|ee)-)?(.+)$/

// 全局刻度(单位 4 px): 所有文件中的间距和尺寸数字只能取这些值; 新增档位先改本脚本之外的规范文档再改这里
const SPACING_SCALE = new Set(['0', '1', '2', '3', '4', '5', '6', '8', '10', '12'])
const SIZE_SCALE = new Set(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '16', '18', '24', '40', '64'])
const SPACING_PREFIX = new Set(['p', 'px', 'py', 'pt', 'pr', 'pb', 'pl', 'ps', 'pe', 'm', 'mx', 'my', 'mt', 'mr', 'mb', 'ml', 'ms', 'me', 'gap', 'space', 'inset', 'top', 'right', 'bottom', 'left', 'start', 'end'])
const SIZE_PREFIX = new Set(['size', 'w', 'h'])

const isNumber = (value) => /^\d+$/.test(value)
const colorOk = (value) => colors.has(value)

// 返回错误信息, 合法时返回 null
function checkUtility(raw) {
  // 去掉变体, 重要标记和负号
  let depth = 0
  let start = 0
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] === '[' || raw[i] === '(') depth++
    else if (raw[i] === ']' || raw[i] === ')') depth--
    else if (raw[i] === ':' && depth === 0) start = i + 1
  }
  let u = raw.slice(start).replace(/^!|!$/g, '').replace(/^-/, '')
  if (!u) return null

  if (/^\[[a-z-]+:.+\]$/.test(u) || u.includes('-[')) return '禁止任意值; 把数值加入 tokens.css 后使用标记'
  if (/-\d+\.\d+$/.test(u)) return '间距和尺寸必须是 4 px 的整数倍, 禁止小数刻度'
  if (/^(duration|delay)-/.test(u)) return '禁止时长工具类; 在样式中使用 var(--duration-*)'
  if (/^tracking-/.test(u)) return '没有字间距标记; 需要时先加入 tokens.css'

  // 颜色修饰 /NN 只对颜色类有意义, 分数尺寸如 top-1/2 不受影响
  const withoutAlpha = u.replace(/\/\d+$/, '')
  const parts = withoutAlpha.match(/^([a-z]+(?:-offset)?)-(.+)$/)
  if (!parts) {
    if (u === 'rounded') return '写明圆角标记, 如 rounded-md'
    if (u === 'shadow') return '写明阴影标记, 如 shadow-sm'
    return null
  }
  const [, prefix, value] = parts

  // 只校验纯数字档位; full, auto, 分数和 CSS 变量简写不受影响
  const numeric = (text) => text.replace(/^[xy]-/, '').replace(/^[wh]-/, '')
  if (SPACING_PREFIX.has(prefix) && isNumber(numeric(value)) && !SPACING_SCALE.has(numeric(value))) {
    return `间距 ${prefix}-${value} 不在刻度 ${[...SPACING_SCALE].join(', ')} (单位 4 px) 内`
  }
  if ((SIZE_PREFIX.has(prefix) || prefix === 'min' || (prefix === 'max' && /^h-/.test(value))) && isNumber(numeric(value)) && !SIZE_SCALE.has(numeric(value))) {
    return `尺寸 ${prefix}-${value} 不在刻度 ${[...SIZE_SCALE].join(', ')} (单位 4 px) 内`
  }

  switch (prefix) {
    case 'text':
      return textSizes.has(value) || colorOk(value) || TEXT_KEYWORDS.has(value) ? null : `未定义的字号或颜色 text-${value}`
    case 'bg':
      return colorOk(value) || BG_KEYWORDS.has(value) ? null : `未定义的背景色 bg-${value}`
    case 'border': {
      if (isNumber(value) || BORDER_KEYWORDS.has(value) || colorOk(value)) return null
      if (/^[xytrblse](-\d+)?$/.test(value)) return null
      const side = value.match(/^[xytrblse]-(.+)$/)
      if (side && colorOk(side[1])) return null
      if (value.startsWith('spacing-')) return null
      return `未定义的边框值 border-${value}`
    }
    case 'ring':
      return isNumber(value) || value === 'inset' || colorOk(value) ? null : `未定义的 ring-${value}`
    case 'ring-offset':
    case 'outline-offset':
      return isNumber(value) || colorOk(value) ? null : `未定义的 ${prefix}-${value}`
    case 'outline':
      return isNumber(value) || OUTLINE_KEYWORDS.has(value) || colorOk(value) ? null : `未定义的 outline-${value}`
    case 'divide':
      return /^[xy](-\d+)?$/.test(value) || value === 'reverse' || BORDER_KEYWORDS.has(value) || colorOk(value)
        ? null
        : `未定义的 divide-${value}`
    case 'shadow':
      return shadows.has(value) || value === 'none' || colorOk(value) ? null : `未定义的阴影 shadow-${value}`
    case 'fill':
    case 'stroke':
      return colorOk(value) || value === 'none' || (prefix === 'stroke' && isNumber(value)) ? null : `未定义的 ${prefix}-${value}`
    case 'from':
    case 'via':
    case 'to':
      return colorOk(value) || /^\d+%$/.test(value) ? null : `未定义的渐变颜色 ${prefix}-${value}`
    case 'decoration':
      return colorOk(value) || DECORATION_KEYWORDS.has(value) || isNumber(value) ? null : `未定义的 decoration-${value}`
    case 'accent':
    case 'caret':
    case 'placeholder':
      return colorOk(value) || value === 'auto' ? null : `未定义的颜色 ${prefix}-${value}`
    case 'rounded': {
      const [, , size] = value.match(RADIUS_SIDES)
      return radii.has(size) || size === 'none' ? null : `未定义的圆角 rounded-${value}; 写明 rounded-md 等标记`
    }
    case 'font':
      return weights.has(value) || families.has(value) ? null : `未定义的字体或字重 font-${value}`
    case 'leading':
      return leadings.has(value) ? null : `未定义的行高 leading-${value}`
    case 'ease':
      return eases.has(value) || value === 'linear' ? null : `未定义的缓动 ease-${value}`
    case 'max': {
      const w = value.match(/^w-([a-z]+)$/)
      if (!w) return null
      return containers.has(w[1]) || set('none full min max fit screen px auto').has(w[1]) ? null : `未定义的容器宽度 max-w-${w[1]}`
    }
  }
  return null
}

const CHECKED_PREFIX =
  /^(text|bg|border|ring|outline|divide|shadow|fill|stroke|from|via|to|decoration|accent|caret|placeholder|rounded|font|leading|ease|max-w|duration|delay|tracking|(?:p[xytrblse]?|m[xytrblse]?|gap|space|size|w|h|min|max|top|right|bottom|left|inset|start|end)-\d|(?:gap|space|inset)-[xy]-\d|(?:min|max)-[wh]-\d|[a-z-]+-\[|\[|[a-z-]+-\d+\.\d+)/

// ---- CSS 声明规则 ----
const COLOR_PROPS =
  /^(color|background|background-color|border(-(top|right|bottom|left|block|inline))?-color|outline-color|fill|stroke|caret-color|accent-color|text-decoration-color)$/
const VAR_ONLY_PROPS = /^(font-size|font-weight|font-family|line-height|letter-spacing|border-radius|box-shadow|z-index)$/
const COLOR_KEYWORDS = /^(transparent|currentcolor|inherit|initial|unset|none)$/i
const LITERAL_UNIT = /(?<![\w-])-?\d*\.?\d+(px|rem|em|ms|s|pt|ch)\b/g

function checkDeclaration(prop, value) {
  const v = value.trim()
  if (COLOR_PROPS.test(prop)) {
    if (!(COLOR_KEYWORDS.test(v) || /^var\(--[\w-]+\)$/.test(v))) return `${prop} 必须使用 var(--颜色标记)`
    return null
  }
  if (VAR_ONLY_PROPS.test(prop)) {
    if (!/var\(--/.test(v) && !/^(inherit|initial|unset|none|0|auto)$/.test(v)) return `${prop} 必须使用 var(--标记)`
  }
  for (const match of v.matchAll(LITERAL_UNIT)) {
    if (match[0] === '1px' || /^-?0+(\.0+)?[a-z]+$/.test(match[0])) continue
    return `写死的数值 ${match[0]}; 在 tokens.css 定义标记后用 var() 引用`
  }
  return null
}

// ---- 页面结构规则 ----
// 适用于 src/components/ 以外的 .vue 文件(页面), App.vue 除外. 页面只组合共享组件, 不自己画控件, 表面和栅格.
const NATIVE_ELEMENTS = {
  input: 'Input, PasswordInput, DateTimePicker, CheckboxField, SwitchField, RangeSlider',
  select: 'SelectMenu(超过 5 项)或 SegmentedControl(不超过 5 项)',
  textarea: 'Textarea',
  button: 'Button',
  table: 'DataTable',
  dialog: 'AppDialog',
  label: 'FormField',
  form: 'CardForm(把几张卡片连成一个表单)',
  h1: 'PageHeader',
  h2: 'PageSection 的 title',
  h3: 'PageSection 的 title(一张卡片只放一件事)',
}
// 页面中的间距只用这几档(单位 4 px); 比全局刻度更少
const PAGE_SPACING = new Set(['0', 'px', '1', '2', '3', '4', '6', '8', '12'])
const SPACING_UTILITY = /^(p[xytrblse]?|m[xytrblse]?|gap(-[xy])?|space-[xy])-(.+)$/

function checkPageUtility(token) {
  if (/(^|:)\*:|\[/.test(token)) return `${token}: 页面禁止任意变体和选择器`
  if (/(^|:)-/.test(token)) return `${token}: 页面禁止负外边距`
  const u = token.replace(/^(?:[\w-]+:|\[[^\]]+\]:)+/, '').replace(/^!/, '')
  if (/^(grid-cols|col-span|grid-rows|row-span|col-start|col-end|grid-flow|auto-cols|auto-rows)-/.test(u)) {
    return `${token}: 页面禁止自写栅格; 用 CardGrid 的卡片, 卡片内的 FormField span 和 FormActions`
  }
  if (/^(flex|inline-flex|grid|inline-grid|contents|flex-(row|col|wrap|nowrap)(-reverse)?|items-.+|justify-.+|self-.+|content-.+|gap(-[xy])?-.+|space-[xy]-.+)$/.test(u)) {
    return `${token}: 页面禁止自己排列元素; 排列由卡片栅格决定, 一张卡片放一件事`
  }
  if (/^-?m[xytrblse]?-/.test(u)) {
    return `${token}: 页面禁止外边距; 块和控件的缩进由卡片栅格提供`
  }
  if (/^(bg-card|bg-popover|shadow-)/.test(u)) {
    return `${token}: 页面禁止自写卡片或浮层表面; 用 PageHeader, PageSection, LinkCard, AppDialog`
  }
  if (/^(absolute|fixed|sticky|relative|static)$/.test(u) || /^(top|right|bottom|left|inset(-[xy])?|start|end|z|order|float|columns|aspect|basis|size|h|max-w|max-h|min-h)-/.test(u)) {
    return `${token}: 页面禁止设置尺寸和定位; 卡片大小由 CardGrid 决定, 控件宽度由栏决定`
  }
  if (/^(w|min-w)-/.test(u) && !['w-full', 'min-w-0'].includes(u)) {
    return `${token}: 页面禁止设置宽度; 宽度由栏决定`
  }
  const spacing = u.match(SPACING_UTILITY)
  if (spacing && !['auto', 'full'].includes(spacing[3]) && !PAGE_SPACING.has(spacing[3])) {
    return `${token}: 页面内边距只用 ${[...PAGE_SPACING].join(', ')} 档; 组件内部除外`
  }
  return null
}

function checkPage(file, text) {
  const template = text.match(/<template>([\s\S]*)<\/template>/)
  if (!template) return
  const offset = template.index + '<template>'.length
  const body = template[1]
  for (const match of body.matchAll(/<(input|select|textarea|button|table|dialog|label|form|h1|h2|h3)\b/g)) {
    report(file, text, offset + match.index, `页面禁止原生 <${match[1]}>; 用 ${NATIVE_ELEMENTS[match[1]]}`)
  }
  // 危险操作(红色按钮)必须经过 ConfirmDialog 确认
  if (/variant="destructive"/.test(body) && !/<ConfirmDialog\b/.test(body)) {
    report(file, text, offset + body.indexOf('variant="destructive"'), '危险按钮(variant="destructive")必须作为 ConfirmDialog 的触发按钮, 不能直接执行')
  }
  for (const match of body.matchAll(/\sclass="([^"]*)"/g)) {
    for (const token of match[1].matchAll(/\S+/g)) {
      const error = checkPageUtility(token[0])
      if (error) report(file, text, offset + match.index + match[0].indexOf(match[1]) + token.index, error)
    }
  }
  for (const match of body.matchAll(/\s:class="([^"]*)"/g)) {
    for (const token of match[1].matchAll(/[\w:-]+(?:-[\w-]+)+/g)) {
      const error = checkPageUtility(token[0])
      if (error) report(file, text, offset + match.index + match[0].indexOf(match[1]) + token.index, error)
    }
  }
}

const componentsDir = join(src, 'components')
const isPage = (file) => file.endsWith('.vue') && !file.startsWith(componentsDir) && file !== join(src, 'App.vue')

// ---- 扫描 ----
function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return walk(path)
    return /\.(vue|ts|tsx|js|css)$/.test(entry.name) ? [path] : []
  })
}

const problems = []

function lineOf(text, index) {
  return text.slice(0, index).split('\n').length
}

function report(file, text, index, message) {
  const line = lineOf(text, index)
  if (text.split('\n')[line - 1].includes(IGNORE)) return
  problems.push(`${relative(root, file)}:${line}: ${message}`)
}

function checkClassTokens(file, text, content, offset) {
  for (const match of content.matchAll(/[^\s'"`,(){}]+/g)) {
    const token = match[0]
    // 跳过模板插值和属性名(如 SVG 字符串中的 stroke-width=)
    if (token.includes('${') || token.includes('=') || !CHECKED_PREFIX.test(token.replace(/^[!-]/, '').replace(/^(?:[\w-]+:|\[[^\]]+\]:)+/, ''))) continue
    const error = checkUtility(token)
    if (error) report(file, text, offset + match.index, `${token}: ${error}`)
  }
}

function checkCss(file, text, css, offset) {
  for (const match of css.matchAll(/([a-z-]+)\s*:\s*([^;{}]+);/g)) {
    if (match[1].startsWith('--')) continue
    const error = checkDeclaration(match[1], match[2])
    if (error) report(file, text, offset + match.index, error)
  }
  for (const match of css.matchAll(/@apply\s+([^;]+);/g)) {
    checkClassTokens(file, text, match[1], offset + match.index + match[0].indexOf(match[1]))
  }
}

for (const file of walk(src)) {
  if (file === tokensPath) continue
  const text = readFileSync(file, 'utf8')

  for (const match of text.matchAll(/#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb|color-mix|color)\(/g)) {
    report(file, text, match.index, `写死的颜色 ${match[0]}; 使用语义颜色标记`)
  }

  if (file.endsWith('.css')) {
    checkCss(file, text, text, 0)
    continue
  }

  if (isPage(file)) checkPage(file, text)

  if (file.endsWith('.vue')) {
    for (const match of text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) {
      checkCss(file, text, match[1], match.index + match[0].indexOf(match[1]))
    }
    for (const match of text.matchAll(/\sstyle="[^"]*"/g)) {
      report(file, text, match.index, '禁止静态 style 属性; 使用工具类, 动态值用 :style')
    }
  }

  const code = file.endsWith('.vue') ? text.replace(/<style[^>]*>[\s\S]*?<\/style>/g, (block) => ' '.repeat(block.length)) : text
  for (const match of code.matchAll(/(["'`])((?:\\.|(?!\1)[^\\])*?)\1/gs)) {
    checkClassTokens(file, text, match[2], match.index + 1)
  }
}

if (problems.length) {
  console.error(`设计检查失败: ${problems.length} 处问题. 只能使用 src/styles/tokens.css 中的标记, 页面只能组合 src/components/ 中的组件.\n`)
  console.error(problems.join('\n'))
  process.exit(1)
}
console.log('设计检查通过')
