import { defineConfig } from '@playwright/test'

// 视觉测试: 构建生产资源后在环回地址运行 Python 控制台(项目决策 2026-11-18, 见 doc/LOG.md).
// 桌面和手机各用一个控制台实例和临时状态目录, 互不影响. 控制台只提供 HTTPS(自签名证书). 端口被占用时设置 E2E_PORT.
const port = Number(process.env.E2E_PORT || 4317)
const base = (process.env.APP_BASE_PATH || '/').replace(/\/?$/, '/')

const PROJECTS = [
  { name: 'desktop', port, use: { viewport: { width: 1280, height: 800 } } },
  {
    name: 'mobile',
    port: port + 1,
    use: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true },
  },
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
    reducedMotion: 'reduce',
    deviceScaleFactor: 1,
    ignoreHTTPSErrors: true,
  },
  projects: PROJECTS.map((project) => ({ name: project.name, use: { ...project.use, baseURL: url(project.port) } })),
  webServer: servers,
})
