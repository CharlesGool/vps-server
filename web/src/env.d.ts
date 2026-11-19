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
    titleKey: string
    icon: PageIcon
    public?: boolean
  }
}

export {}
