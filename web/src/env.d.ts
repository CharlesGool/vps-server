/// <reference types="vite/client" />

import type { PageIcon } from './routes'

declare global {
  const __APP_VERSION__: string
  interface ImportMetaEnv {
    readonly VITE_E2E?: string
  }
}

declare module 'vue-router' {
  interface RouteMeta {
    // 还由服务器生成的旧页面, 整页跳转
    legacy?: boolean
    titleKey: string
    icon: PageIcon
    public?: boolean
  }
}

export {}
