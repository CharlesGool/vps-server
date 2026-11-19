import { createApp } from 'vue'
import App from './App.vue'
import { initAppearance } from './lib/appearance'
import { i18n, initLocale } from './lib/i18n'
import { initResizeReflow } from './lib/resize-reflow'
import { initSession } from './lib/session'
import { showToast } from './lib/toast'
import { router } from './router'
import './styles/main.css'

initAppearance()
initLocale()
initResizeReflow()
initSession(() => router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } }))

// 视觉测试构建(VITE_E2E=1)时让测试能触发通知
if (import.meta.env.VITE_E2E) Object.assign(window, { __showToast: showToast })

createApp(App).use(i18n).use(router).mount('#app')
