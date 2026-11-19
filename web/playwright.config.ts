import { defineConfig } from '@playwright/test'

// 视觉测试: 构建生产资源后在环回地址运行 Python 控制台(项目决策 2026-11-18, 见 doc/LOG.md).
// 桌面, 手机和项目功能测试各用一个控制台实例和临时状态目录, 互不影响. 控制台只提供 HTTPS(自签名证书). 端口被占用时设置 E2E_PORT.
const port = Number(process.env.E2E_PORT || 4317)
const base = (process.env.APP_BASE_PATH || '/').replace(/\/?$/, '/')

// vps-project: vps-server 自己的功能测试(e2e/vps-*.spec.ts)会改变控制台状态(测速产生流量, 修改流量限制),
// 所以用第三个实例, 不影响桌面和手机的截图和布局检查; 其他两个项目不运行这些文件.
const VPS_TESTS = /[\\/]e2e[\\/]vps-[^\\/]*\.spec\.ts$/
const PROJECTS = [
  { name: 'desktop', port, testIgnore: VPS_TESTS, use: { viewport: { width: 1280, height: 800 } } },
  {
    name: 'mobile',
    port: port + 1,
    testIgnore: VPS_TESTS,
    use: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true },
  },
  { name: 'vps', port: port + 2, testMatch: VPS_TESTS, use: { viewport: { width: 1280, height: 800 } } },
]
const url = (p: number) => `https://127.0.0.1:${p}${base}`

// 第一个实例负责构建前端
function pythonServer(p: number, index: number) {
  return {
    command: `${index === 0 ? 'npm run build && ' : ''}node scripts/e2e-server.mjs ${p}`,
    url: url(p),
    ignoreHTTPSErrors: true,
    env: { APP_VERSION: 'e2e', VITE_E2E: '1', APP_BASE_PATH: base },
    reuseExistingServer: false,
    timeout: 180_000,
  }
}

const servers = PROJECTS.map((project, index) => pythonServer(project.port, index))

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: true,
  reporter: [['list']],
  // 截图基准按平台分开保存, 字体渲染随操作系统不同
  snapshotPathTemplate: '{testDir}/__screenshots__/{platform}/{projectName}/{arg}{ext}',
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: 'disabled', caret: 'hide', scale: 'css' },
  },
  use: {
    browserName: 'chromium',
    locale: 'zh-CN',
    // vps-server: 部分页面按浏览器时区显示时间(如迷你网盘的添加时间), 固定时区让截图和主机无关
    timezoneId: 'UTC',
    reducedMotion: 'reduce',
    deviceScaleFactor: 1,
    ignoreHTTPSErrors: true,
    // 控制台用自签名证书. 只设 ignoreHTTPSErrors 时 Chromium 先以"证书未知"中断每次 TLS 握手再重连,
    // 并发时有请求因此重试到放弃(ERR_TOO_MANY_RETRIES); 在网络层直接接受证书.
    launchOptions: { args: ['--ignore-certificate-errors'] },
  },
  projects: PROJECTS.map(({ name, use, testIgnore, testMatch, port: p }) => ({
    name,
    testIgnore,
    testMatch,
    use: { ...use, baseURL: url(p) },
  })),
  webServer: servers,
})
