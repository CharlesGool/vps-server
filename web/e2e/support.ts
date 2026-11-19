import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, type Page, test as base } from '@playwright/test'
import { E2E_PASSWORD } from './password'
import { FEATURES } from '../src/app.config'
import { appRoutes } from '../src/routes'
import { RESOURCES_SAMPLE, SYSTEM_ROUTES } from './system-samples'

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

const VISITORS_SAMPLE = {
  max: 1000,
  rows: Array.from({ length: 12 }, (_, index) => ({
    ip: index === 0 ? '127.0.0.1' : index < 4 ? `192.168.1.${10 + index}` : `203.0.113.${20 + index}`,
    scope: index === 0 ? 'loopback' : index < 4 ? 'private' : 'public',
    direction: index % 5 === 4 ? 'out' : 'in',
    firstSeen: `2026-01-0${(index % 9) + 1}T08:00:00+00:00`,
    lastSeen: `2026-01-1${index % 10}T09:30:00+00:00`,
    hits: index % 5 === 4 ? 0 : 3 * index + 1,
    ports: index % 3 === 0 ? '22, 443' : '443',
    lastRequest: index % 5 === 4 ? '' : 'GET /api/session → 200',
  })),
}

const GIB = 1024 ** 3
const FILES_SAMPLE = {
  used: 1.5 * GIB,
  quota: 5 * GIB,
  room: 3.5 * GIB,
  diskFree: 40 * GIB,
  rate: 0,
  linkMinutes: [5, 10, 30, 60, 120, 300, 1440, 10080, 43200, 0],
  defaultLinkMinutes: 10080,
  message: null,
  files: [
    { id: 'f1', name: 'backup-2026-01-01.tar.gz', size: 1.2 * GIB, created: 1767254400, source: 'upload', links: [] },
    {
      id: 'f2',
      name: 'sing-box-1.13.21-linux-amd64.tar.gz',
      size: 0.3 * GIB,
      created: 1767168000,
      source: 'https://github.com/SagerNet/sing-box/releases/download/v1.13.21/sing-box-1.13.21-linux-amd64.tar.gz',
      links: [{ token: 'sample-token', url: 'https://127.0.0.1/f/sample-token/sing-box.tar.gz', expires: 1767772800, downloads: 2, max: 5 }],
    },
  ],
  jobs: [
    { id: 'j1', name: 'debian-13.iso', url: 'https://example.com/debian-13.iso', state: 'failed', bytes: 0, total: null, error: 'network' },
    { id: 'j2', name: 'release.zip', url: 'https://example.com/release.zip', state: 'done', bytes: 52428800, total: 52428800, error: '' },
  ],
}

const BACKUP_SAMPLE = {
  settings: { enabled: true, spec: { mode: 'daily', time: '03:00:00' }, keep: 7, text: '每天 03:00' },
  keepMax: 100,
  last: { status: 'ok', started: '2026-01-02 03:00', exit: null, trigger: 'schedule', output: '' },
  next: '2026-01-03 03:00',
  backups: [
    { name: 'vps-server-20260102T030000Z-scheduled.tar.gz.sealed', kind: 'scheduled', sealed: true, keyMatch: true, created: '2026-01-02 03:00', size: 184320 },
    { name: 'vps-server-20260101T120000Z-pre-upgrade.tar.gz', kind: 'pre-upgrade', sealed: false, keyMatch: null, created: '2026-01-01 12:00', size: 176128 },
    { name: 'vps-server-20251231T080000Z-manual.tar.gz.sealed', kind: 'manual', sealed: true, keyMatch: false, created: '2025-12-31 08:00', size: 172032 },
  ],
  encryption: { on: true, fingerprint: 'a1b2c3d4e5f6' },
  data: { state: 'on', encrypted: 9, total: 9 },
  result: { ok: true, time: '2026-01-01 12:05', name: 'vps-server-20260101T120000Z-pre-upgrade.tar.gz', restored: 42, error: '' },
  timezone: 'UTC',
  message: null,
}
const TASKS_SAMPLE = {
  backup: {
    enabled: true,
    text: '每天 03:00',
    next: '2026-01-03 03:00',
    last: { status: 'ok', started: '2026-01-02 03:00', exit: null, trigger: 'schedule', output: '' },
    runs: [{ status: 'ok', started: '2026-01-02 03:00', exit: null, trigger: 'schedule', output: '' }],
  },
  tasks: [
    {
      id: '0a1b2c3d',
      name: '清理日志',
      command: 'journalctl --vacuum-time=7d',
      timeout: 600,
      notify: true,
      enabled: true,
      spec: { mode: 'weekly', days: [1, 4], time: '04:30:00' },
      text: '每周一、四 04:30',
      next: '2026-01-05 04:30',
      done: null,
      last: { status: 'ok', started: '2026-01-01 04:30', exit: 0, trigger: 'schedule', output: 'Vacuuming done, freed 120.0M.' },
      runs: [{ status: 'ok', started: '2026-01-01 04:30', exit: 0, trigger: 'schedule', output: 'Vacuuming done, freed 120.0M.' }],
    },
    {
      id: '4e5f6a7b',
      name: '检查更新',
      command: 'apt-get update -qq',
      timeout: 3600,
      notify: false,
      enabled: false,
      spec: { mode: 'interval', n: 6, unit: 'hours' },
      text: '每 6 小时',
      next: null,
      done: null,
      last: { status: 'failed', started: '2026-01-01 06:00', exit: 100, trigger: 'manual', output: 'E: Could not get lock /var/lib/apt/lists/lock' },
      runs: [{ status: 'failed', started: '2026-01-01 06:00', exit: 100, trigger: 'manual', output: 'E: Could not get lock /var/lib/apt/lists/lock' }],
    },
  ],
  limits: { nameMax: 60, commandMax: 2000, timeoutMin: 1, timeoutMax: 86400, timeoutDefault: 3600 },
  timezone: 'UTC',
  message: null,
}

const TAILSCALE_SAMPLE = {
  installed: true,
  available: true,
  state: 'Running',
  version: '1.104.5',
  tun: true,
  present: { controlServer: true, ipv4: true, ipv6: true, account: true },
  authUrl: null,
  settings: {
    bools: { 'accept-dns': true, 'accept-routes': false, 'advertise-exit-node': true, 'exit-node-allow-lan-access': false, 'shields-up': false, 'snat-subnet-routes': true, ssh: false, webclient: false },
    routes: '',
    exit: '',
    relay: false,
    memory: false,
  },
  subnets: ['10.0.0.0/24'],
  exitNodes: [{ value: 'home-router.tail1234.ts.net', label: 'home-router' }],
  devices: [
    { id: 'n1', name: 'laptop', online: true, os: 'macOS', relay: 'tok', rx: 52428800, tx: 10485760, lastSeen: '', ipv4: true, ipv6: true },
    { id: 'n2', name: 'home-router', online: false, os: 'linux', relay: '', rx: 0, tx: 0, lastSeen: '2026-01-01T08:00:00Z', ipv4: true, ipv6: false },
  ],
}
const NETCHECK_SAMPLE = {
  running: true,
  derp: '7',
  endpoint: true,
  checks: { varies: false, ipv4: true, ipv6: true, udp: true, upnp: false, pcp: false, pmp: false, hairpinning: null },
}

const site = (host: string, extra: Record<string, unknown> = {}) => ({
  host,
  zone: 'example.com',
  enabled: true,
  console: false,
  hasPort: true,
  scheme: 'http',
  backendTls: false,
  upstreamHost: false,
  options: '',
  aliases: [],
  allowIps: [],
  authUser: '',
  addedAt: '2026-01-01',
  badges: [
    { tone: 'success', text: '证书有效' },
    { tone: 'success', text: 'DNS 已同步' },
  ],
  certText: "Let's Encrypt, 有效至 2026-03-01(剩 59 天), 到期前自动续期",
  dnsText: 'A 记录指向本机, 仅 DNS; 最近同步 2026-01-02 08:00',
  aliasesText: '',
  accessText: '不限制',
  ...extra,
})
const DOMAINS_SAMPLE = {
  installed: true,
  running: true,
  dns: { ipv4: true, ipv6: false, checked: '2026-01-02 08:00', error: null },
  history: [{ time: '01-02 08:00', text: '已添加 nas.example.com' }],
  zones: ['example.com'],
  consoleTarget: true,
  groups: [
    {
      zone: 'example.com',
      sites: [
        site('nas.example.com', { backendTls: true, scheme: 'https', options: '后端 HTTPS' }),
        site('panel.example.com', { console: true, hasPort: false }),
        site('old.example.com', { enabled: false, badges: [{ tone: 'neutral', text: '已停用' }, { tone: 'neutral', text: '证书申请中' }] }),
      ],
    },
  ],
  tokens: [{ id: 't1', name: '主账号', state: 'ok', checked: '2026-01-02 08:00', zones: [{ zone: 'example.com', sites: 3 }] }],
  message: null,
  warning: null,
}
const IPCERT_SAMPLE = {
  installed: true,
  enabled: true,
  facts: { url: 'https://203.0.113.10:28211/', issuer: "Let's Encrypt", expires: '2026-01-08 08:00 (剩 6 天, 自动续期)' },
  job: null,
}

const JAN_2 = 1767340800
function securitySample() {
  return {
    securityUntil: new Date(Date.now() + 600_000).toISOString(),
    ipAccess: { enabled: true, allowlist: ['192.168.1.20'], loadError: false },
    certificates: { mode: 'either', modes: ['password', 'cert', 'either', 'both'], current: null, currentSetup: [], items: [] },
    loginBan: {
      enabled: true,
      loadError: false,
      window: 60,
      maxAttempts: 5,
      lockout: 30,
      lockoutMax: 86400,
      globalMaxAttempts: 20,
      globalLockout: 300,
      globalState: 'normal',
      globalRemaining: 0,
      sources: [],
    },
    consoleAccess: { enabled: false, loadError: false, networks: [], current: '127.0.0.1', currentListed: true, recovery: 'python3 /opt/vps-server/web/console_access.py disable' },
    sessions: {
      ttl: 43200,
      idle: 7200,
      items: [
        { id: 's1', current: true, ip: '127.0.0.1', agent: '', method: 'password', created: JAN_2, seen: JAN_2 + 60, device: '' },
        { id: 's2', current: false, ip: '192.168.1.20', agent: '', method: 'ip', created: JAN_2 - 3600, seen: JAN_2 - 600, device: '' },
      ],
    },
    alerts: { server: 'https://api.day.app', configured: false, newIp: true, ban: true, loadError: false },
    audit: [
      { t: JAN_2 + 60, event: 'login_new_ip', ip: '127.0.0.1', detail: 'password' },
      { t: JAN_2, event: 'login_ok', ip: '127.0.0.1', detail: 'password' },
      { t: JAN_2 - 3600, event: 'login_fail', ip: '203.0.113.9', detail: 'password' },
    ],
  }
}

const FRPS_SAMPLE = {
  installed: true,
  node: { running: true, bind: '0.0.0.0', addresses: [{ index: 0, label: 'eth0 (IPv4)' }, { index: 1, label: 'eth0 (IPv6)' }] },
}
const FRPC_SAMPLE = {
  installed: true,
  binaryMissing: false,
  clients: [
    { name: 'home', running: true, connected: true, count: 2, proxies: [{}, {}], visitors: [] },
    { name: 'office', running: false, connected: false, count: 1, proxies: [{}], visitors: [{}] },
  ],
}

const PROXY_SAMPLE = {
  installed: true,
  available: true,
  running: true,
  protocols: ['anytls', 'vmess', 'vless', 'trojan', 'shadowsocks'],
  share: true,
  addresses: [{ index: 0, label: 'eth0 (IPv4)' }],
  nodes: [
    { id: 'n1', number: 1, name: '家里', protocol: 'anytls', enabled: true, active: true, sni: 'www.bing.com', route: '不限制', access: { mode: 'all', destinations: [] } },
    { id: 'n2', number: 2, name: '备用', protocol: 'shadowsocks', enabled: false, active: false, sni: null, route: '仅公网(禁止内网)', access: { mode: 'internet', destinations: [] } },
  ],
  message: null,
}

// 每个测试都检查控制台错误和未捕获异常
export const test = base.extend<{ consoleErrors: string[]; stableServer: void }>({
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
  // vps-server(项目决策 2026-11-18): 有两处服务器内容会随运行变化, 截图和布局检查里换成固定内容; 项目自己的测试(vps 项目)用真实服务器.
  // 终端页连接真实的 root shell: 并发打开很多页面会占满终端名额(429), 输出也随环境变化, 所以用固定的提示符代替.
  // 最近访问者记录每次请求的时间: 用固定的 12 行样例(含本机, 内网, 外部, 入站, 出站, 第二页).
  // 迷你网盘显示本机磁盘剩余空间: 用固定样例(含文件, 下载链接, 进行中和失败的下载任务).
  // 备份和定时任务显示下次运行的日期和服务器时区: 用固定样例(含几份备份, 两个任务和运行记录).
  // Tailscale, 域名转发(Caddy), FRPS, FRPC 和 Singbox 在测试服务器上没有安装: 用已在使用的样例, 检查真正的管理界面.
  // 资源监控, 系统, 文件管理和多主机显示本机实时数据(CPU, 进程, 服务, 端口, 文件): 用 system-samples.ts 的固定样例; 主页只替换 resources.
  stableServer: [
    async ({ page }, use, testInfo) => {
      // 截图对比里安全设置的登录设备数和安全记录取决于之前有多少测试登录过: 只在截图测试里用固定样例(其他测试要真实的安全设置)
      if (testInfo.project.name !== 'vps' && testInfo.file.endsWith('visual.spec.ts')) {
        await page.route(/\/api\/security$/, (route) =>
          route.request().method() === 'GET' ? route.fulfill({ json: securitySample() }) : route.fallback(),
        )
      }
      if (testInfo.project.name !== 'vps') {
        await page.routeWebSocket(/\/terminal\/ws/, (socket) => {
          socket.send(Buffer.from('root@vps-server:~# '))
          socket.onMessage(() => {})
        })
        await page.route(/\/api\/visitors$/, (route) =>
          route.request().method() === 'GET' ? route.fulfill({ json: VISITORS_SAMPLE }) : route.fallback(),
        )
        await page.route(/\/api\/files$/, (route) => (route.request().method() === 'GET' ? route.fulfill({ json: FILES_SAMPLE }) : route.fallback()))
        await page.route(/\/api\/backup$/, (route) => (route.request().method() === 'GET' ? route.fulfill({ json: BACKUP_SAMPLE }) : route.fallback()))
        await page.route(/\/api\/tasks$/, (route) => (route.request().method() === 'GET' ? route.fulfill({ json: TASKS_SAMPLE }) : route.fallback()))
        await page.route(/\/api\/tailscale$/, (route) => (route.request().method() === 'GET' ? route.fulfill({ json: TAILSCALE_SAMPLE }) : route.fallback()))
        await page.route(/\/api\/tailscale\/netcheck$/, (route) => route.fulfill({ json: NETCHECK_SAMPLE }))
        await page.route(/\/api\/domains$/, (route) => (route.request().method() === 'GET' ? route.fulfill({ json: DOMAINS_SAMPLE }) : route.fallback()))
        await page.route(/\/api\/ipcert$/, (route) => route.fulfill({ json: IPCERT_SAMPLE }))
        await page.route(/\/api\/frps$/, (route) => route.fulfill({ json: FRPS_SAMPLE }))
        await page.route(/\/api\/frpc$/, (route) => route.fulfill({ json: FRPC_SAMPLE }))
        await page.route(/\/api\/proxy$/, (route) => (route.request().method() === 'GET' ? route.fulfill({ json: PROXY_SAMPLE }) : route.fallback()))
        for (const [pattern, sample] of SYSTEM_ROUTES) {
          await page.route(pattern, (route) => (route.request().method() === 'GET' ? route.fulfill({ json: sample }) : route.fallback()))
        }
        await page.route(/\/api\/dashboard$/, async (route) => {
          if (route.request().method() !== 'GET') return route.fallback()
          // 测试结束时请求可能还在路上: 那时页面已关闭, 忽略即可
          try {
            const response = await route.fetch()
            await route.fulfill({ response, json: { ...(await response.json()), resources: RESOURCES_SAMPLE } })
          } catch {
            // 页面已关闭
          }
        })
      }
      await use()
    },
    { auto: true },
  ],
})
export { expect }
