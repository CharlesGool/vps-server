import { ref, watch } from 'vue'

export const THEMES = ['slate-blue', 'sage', 'teal', 'plum', 'ocean', 'olive', 'terracotta', 'indigo'] as const
export const MODES = ['light', 'dark', 'system'] as const
export type Theme = (typeof THEMES)[number]
export type Mode = (typeof MODES)[number]

const MODE_KEY = 'vps-server-mode'
const THEME_KEY = 'vps-server-theme'

function read<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key) as T | null
    return value && allowed.includes(value) ? value : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // 存储不可用时只在本次会话生效
  }
}

export const mode = ref<Mode>(read(MODE_KEY, MODES, 'light'))
export const theme = ref<Theme>(read(THEME_KEY, THEMES, 'slate-blue'))

const systemDark = matchMedia('(prefers-color-scheme: dark)')

function applyMode() {
  const dark = mode.value === 'dark' || (mode.value === 'system' && systemDark.matches)
  document.documentElement.classList.toggle('dark', dark)
}

export function initAppearance() {
  applyMode()
  document.documentElement.dataset.theme = theme.value
  systemDark.addEventListener('change', applyMode)
  watch(mode, (value) => {
    write(MODE_KEY, value)
    applyMode()
  })
  watch(theme, (value) => {
    write(THEME_KEY, value)
    document.documentElement.dataset.theme = value
  })
}
