import { createI18n } from 'vue-i18n'
import en from '@lang/en.json'
import es from '@lang/es.json'
import zhCN from '@lang/zh-CN.json'
export const i18n = createI18n({legacy: false, flatJson: true, locale: document.documentElement.lang || 'en', fallbackLocale: ['en', 'zh-CN'], messages: {'zh-CN': zhCN, en, es}})
export type Locale = 'zh-CN' | 'en' | 'es'
