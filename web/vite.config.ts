import { execSync } from 'node:child_process'
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 构建版本: 正式构建由 APP_VERSION 传入, 否则为 test-<short SHA>.
function buildVersion(): string {
  if (process.env.APP_VERSION) return process.env.APP_VERSION
  try {
    return `test-${execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()}`
  } catch {
    return 'test-dev'
  }
}

const base = (process.env.APP_BASE_PATH || '/').replace(/\/?$/, '/')

export default defineConfig({
  base,
  plugins: [vue(), tailwindcss()],
  define: { __APP_VERSION__: JSON.stringify(buildVersion()) },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@lang': fileURLToPath(new URL('../lang/ui', import.meta.url)),
    },
  },
  server: {
    fs: { allow: ['..'] },
    // 开发时 API 请求转发到 Python 控制台(HTTPS 自签名证书)
    proxy: { [`${base}api`]: { target: `https://127.0.0.1:${process.env.API_PORT || 8080}`, secure: false } },
  },
})
