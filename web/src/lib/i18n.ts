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

function initialLocale(): Locale {
  try {
    const saved = localStorage.getItem(LOCALE_KEY) as Locale | null
    if (saved && LOCALES.includes(saved)) return saved
  } catch {
    // 忽略存储错误
  }
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
  watch(locale, (value) => {
    document.documentElement.lang = value
    try {
      localStorage.setItem(LOCALE_KEY, value)
    } catch {
      // 忽略存储错误
    }
  })
}
