import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError, isSignedOut } from './api'
import { showToast } from './toast'

// 需要管理员验证的页面(系统, 文件管理, 多主机): 和终端一样, 最近几分钟内验证过管理员密码才能读写.
// state: loading → ready, 或 verify(要输入密码) / ip(IP 免密会话, 只能说明需要用密码登录).
// guard(fn) 执行一次请求: 验证过期时切回 verify, 其他错误按 errorKey 提示; 返回请求结果或 undefined.
export type Guard = <T>(fn: () => Promise<T>, errorKey?: (code: string) => string | undefined) => Promise<T | undefined>

export function useSecurePage() {
  const { t } = useI18n()
  const state = ref<'loading' | 'verify' | 'ip' | 'ready'>('loading')

  const guard: Guard = async (fn, errorKey) => {
    try {
      const result = await fn()
      if (state.value === 'loading') state.value = 'ready'
      return result
    } catch (err) {
      if (err instanceof ApiError && err.code === 'security_required') state.value = 'verify'
      else if (err instanceof ApiError && err.code === 'password_session_required') state.value = 'ip'
      else if (!isSignedOut(err)) {
        const code = err instanceof ApiError ? err.code : ''
        showToast(errorKey?.(code) ?? t('vps.common.failed'), 'destructive')
      }
      return undefined
    }
  }
  return { state, guard }
}
