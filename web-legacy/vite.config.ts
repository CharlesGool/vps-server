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

export default defineConfig({
  base: '/static/',
  build: {lib: {entry: 'src/main.ts', formats: ['es'], fileName: () => 'ui.js', cssFileName: 'ui'}, sourcemap: false},
  plugins: [vue(), tailwindcss()],
  define: { __APP_VERSION__: JSON.stringify(buildVersion()),
    'process.env.NODE_ENV': JSON.stringify('production'),
    __VUE_OPTIONS_API__: false, __VUE_PROD_DEVTOOLS__: false,
    __VUE_I18N_FULL_INSTALL__: true, __VUE_I18N_LEGACY_API__: false,
    __INTLIFY_PROD_DEVTOOLS__: false,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@lang': fileURLToPath(new URL('../lang/web', import.meta.url)),
    },
  },
  server: { fs: { allow: ['..'] } },
})
