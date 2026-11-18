import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, type Page, test as base } from '@playwright/test'
import { E2E_PASSWORD } from './password'
import { FEATURES } from '../src/app.config'
import { appRoutes } from '../src/routes'

// 测试共用: 路由, 设计标记, 外观设置, 页面加载. 路由和标记都从源码读取, 新增后无需修改测试.
const web = join(import.meta.dirname, '..')
const read = (path: string) => readFileSync(join(web, path), 'utf8')

export const MODES = ['light', 'dark'] as const
export const THEMES = [...read('src/lib/appearance.ts').match(/THEMES = \[([^\]]+)\]/)![1]!.matchAll(/'([^']+)'/g)].map(
  (match) => match[1]!,
)
export const LOCALES = [...read('src/lib/i18n.ts').match(/LOCALES = \[([^\]]+)\]/)![1]!.matchAll(/'([^']+)'/g)].map(
  (match) => match[1]!,
)
export type Mode = (typeof MODES)[number]

export { E2E_PASSWORD, FEATURES }

// src/routes.ts 中按当前开关启用的静态路径; 带参数的路由在 e2e/routes.json 的 extra 中写出示例路径.
function routes(): string[] {
  const statics = appRoutes()
    .map((route) => route.path)
    .filter((path) => !/[:*(]/.test(path))
  let extra: string[] = []
  try {
    extra = JSON.parse(read('e2e/routes.json')).extra ?? []
  } catch {
    // 没有 routes.json
  }
  return [...new Set([...statics, ...extra])]
}
export const ROUTES = routes()
// 部署基础路径, 与 vite.config.ts 一致
export const BASE_PATH = (process.env.APP_BASE_PATH || '/').replace(/\/?$/, '/')

// 从 tokens.css 读取允许的数值
const tokensCss = read('src/styles/tokens.css')
function tokenValues(prefix: string): Map<string, string> {
  const values = new Map<string, string>()
  for (const match of tokensCss.matchAll(new RegExp(`--${prefix}-([a-z0-9-]+)\\s*:\\s*([^;]+);`, 'g'))) {
    if (!match[1]!.includes('--')) values.set(match[1]!, match[2]!.trim())
  }
  return values
}
const px = (value: string) => Number.parseFloat(value)
export const TOKENS = {
  textSizes: [...tokenValues('text').values()].filter((value) => value.endsWith('px')).map(px),
  weights: [...tokenValues('font-weight').values()].map(Number),
  radii: [...tokenValues('radius').values()].map(px),
  spacing: px(tokensCss.match(/--spacing:\s*([^;]+);/)![1]!),
  fonts: [...tokenValues('font').entries()].filter(([name]) => !name.startsWith('weight')).map(([, value]) => value),
  shadows: [...tokenValues('shadow').values()],
  // `@theme inline` 中的语义颜色, 如 --color-primary: var(--primary)
  colors: [...tokenValues('color').entries()]
    .filter(([, value]) => value.startsWith('var('))
    .map(([name, value]) => ({ name, value })),
}

// 卡片栅格, 控件和触控尺寸; 与渲染结果比对
const tokenNumber = (name: string) => px(tokensCss.match(new RegExp(`--${name}:\\s*([^;]+);`))![1]!)
export const DESIGN = {
  cardColumns: tokenNumber('card-columns'),
  maxColumns: tokenNumber('card-max-columns'),
  minCardWidth: tokenNumber('card-min-width'),
  spaceLabel: tokenNumber('space-label'),
  spaceField: tokenNumber('space-field'),
  spaceCard: tokenNumber('space-card'),
  buttonMin: tokenNumber('button-min-width'),
  buttonMax: tokenNumber('button-max-width'),
  rowUnit: tokenNumber('row-unit'),
  controlHeights: ['sm', 'md', 'lg'].map((size) => tokenNumber(`control-height-${size}`)),
  areaHeights: ['md', 'lg'].map((size) => tokenNumber(`area-height-${size}`)),
  touchMin: tokenNumber('touch-target-min'),
  content: tokenNumber('container-content'),
  cardRadius: tokenNumber('radius-lg'),
  // 间距刻度 0, 1, 2, 3, 4, 5, 6, 8, 10, 12 (单位 4 px)
  spacing: [0, 1, 2, 3, 4, 5, 6, 8, 10, 12].map((step) => step * px(tokensCss.match(/--spacing:\s*([^;]+);/)![1]!)),
}

export interface Appearance {
  mode?: Mode
  theme?: string
  locale?: string
}

// 在页面脚本运行前写入外观设置; 默认浅色, 默认主题色, 简体中文.
export async function setAppearance(page: Page, { mode = 'light', theme = THEMES[0], locale = 'zh-CN' }: Appearance) {
  await page.addInitScript(
    ([mode, theme, locale]) => {
      localStorage.setItem('ui.mode', mode!)
      localStorage.setItem('ui.theme', theme!)
      localStorage.setItem('ui.lang', locale!)
    },
    [mode, theme, locale],
  )
  await page.emulateMedia({ colorScheme: mode, reducedMotion: 'reduce' })
}

const PUBLIC = new Set(appRoutes().filter((route) => route.public).map((route) => route.path))

// 启用登录时用测试密码登录; 会话 Cookie 与页面共享
export async function signIn(page: Page) {
  const response = await page.request.post('api/login', { data: { password: E2E_PASSWORD } })
  expect(response.status(), '测试密码登录').toBe(200)
}

// 打开页面并等待渲染稳定; 路径相对部署基础路径. 启用登录时, 受保护的页面先登录.
export async function open(page: Page, path: string, { signedIn = !PUBLIC.has(path) } = {}) {
  if (FEATURES.login && signedIn) await signIn(page)
  await page.goto(path.replace(/^\//, ''))
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => document.fonts.ready)
  await expect(page.locator('#app')).not.toBeEmpty()
}

// 每个测试都检查控制台错误和未捕获异常
export const test = base.extend<{ consoleErrors: string[] }>({
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = []
      page.on('console', (message) => {
        // API 返回的 4xx 是预期结果(如密码错误), 由测试断言; 其他错误都记录
        const expected = /\/api\//.test(message.location().url) && /status of 4\d\d/.test(message.text())
        if (message.type() === 'error' && !expected) errors.push(message.text())
      })
      page.on('pageerror', (error) => errors.push(error.message))
      await use(errors)
      expect(errors, '控制台错误').toEqual([])
    },
    { auto: true },
  ],
})
export { expect }
