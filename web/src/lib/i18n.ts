import en from '@lang/en.json'
import es from '@lang/es.json'
import zhCN from '@lang/zh-CN.json'
import { watch } from 'vue'
import { createI18n } from 'vue-i18n'

export const LOCALES = ['zh-CN', 'en', 'es'] as const
export type Locale = (typeof LOCALES)[number]

// 语言选项显示本名, 不随界面语言翻译.
export const NATIVE_NAMES: Record<Locale, string> = { 'zh-CN': '简体中文', en: 'English', es: 'Español' }

const LOCALE_KEY = 'ui.lang'

// 控制台服务器按 lang Cookie 选语言(服务器生成的页面和提示); 代码与这里的语言名对应.
const SERVER_CODES: Record<Locale, string> = { 'zh-CN': 'zh_cn', en: 'en', es: 'es' }

function serverLocale(): Locale | undefined {
  const code = document.cookie.match(/(?:^|;\s*)lang=([^;]+)/)?.[1]
  return LOCALES.find((locale) => SERVER_CODES[locale] === code)
}

function syncServerLocale(locale: Locale) {
  document.cookie = `lang=${SERVER_CODES[locale]}; Path=/; Max-Age=${365 * 24 * 3600}; SameSite=Lax`
}

function initialLocale(): Locale {
  try {
    const saved = localStorage.getItem(LOCALE_KEY) as Locale | null
    if (saved && LOCALES.includes(saved)) return saved
  } catch {
    // 忽略存储错误
  }
  const server = serverLocale()
  if (server) return server
  for (const tag of navigator.languages) {
    const match = LOCALES.find((locale) => tag === locale || tag.split('-')[0] === locale.split('-')[0])
    if (match) return match
  }
  return 'zh-CN'
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: ['en', 'zh-CN'],
  messages: { 'zh-CN': zhCN, en, es },
})

export function initLocale() {
  const locale = i18n.global.locale
  document.documentElement.lang = locale.value
  syncServerLocale(locale.value as Locale)
  watch(locale, (value) => {
    document.documentElement.lang = value
    syncServerLocale(value as Locale)
    try {
      localStorage.setItem(LOCALE_KEY, value)
    } catch {
      // 忽略存储错误
    }
  })
}
