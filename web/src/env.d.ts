/// <reference types="vite/client" />

declare global {
  const __APP_VERSION__: string
}

declare module 'vue-router' {
  interface RouteMeta {
    titleKey: string
    icon: 'home' | 'settings' | 'changelog'
  }
}

export {}
