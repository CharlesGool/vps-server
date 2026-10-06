#!/usr/bin/env node
// 设计检查: 拒绝绕过设计标记的写法. 只有 src/styles/tokens.css 可以写具体数值.
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
  /^(text|bg|border|ring|outline|divide|shadow|fill|stroke|from|via|to|decoration|accent|caret|placeholder|rounded|font|leading|ease|max-w|duration|delay|tracking|[a-z-]+-\[|\[|[a-z-]+-\d+\.\d+)/

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
  console.error(`设计检查失败: ${problems.length} 处问题. 只能使用 src/styles/tokens.css 中的标记.\n`)
  console.error(problems.join('\n'))
  process.exit(1)
}
console.log('设计检查通过')
