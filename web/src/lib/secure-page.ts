import { ref } from 'vue'
import { ApiError, isSignedOut } from './api'
import { errorText } from './errors'
import { showToast } from './toast'

// 需要管理员验证的页面(系统, 系统更新, 进程, 服务, 监听端口, 文件管理, 集中管理): 和终端一样, 最近几分钟内验证过管理员密码才能读写.
// state: loading → ready, 或 verify(要输入密码) / ip(IP 免密会话, 只能说明需要用密码登录).
// guard(fn) 执行一次请求: 验证过期时切回 verify, 其他错误按 errorKey(按错误码的文案)和 labels(被拒绝的输入项的标签, 见 errors.ts)提示;
// 返回请求结果或 undefined. failure 是最近一次提示过的错误(成功后清空), 页面可用 fieldError 标出对应的输入项.
export type Guard = <T>(
  fn: () => Promise<T>,
  errorKey?: (code: string) => string | undefined,
  labels?: Record<string, string>,
) => Promise<T | undefined>

export function useSecurePage() {
  const state = ref<'loading' | 'verify' | 'ip' | 'ready'>('loading')
  const failure = ref<unknown>()

  const guard: Guard = async (fn, errorKey, labels) => {
    try {
      const result = await fn()
      if (state.value === 'loading') state.value = 'ready'
      failure.value = undefined
      return result
    } catch (err) {
      if (err instanceof ApiError && err.code === 'security_required') state.value = 'verify'
      else if (err instanceof ApiError && err.code === 'password_session_required') state.value = 'ip'
      else if (!isSignedOut(err)) {
        failure.value = err
        showToast(errorText(err, { codes: errorKey, labels }), 'destructive')
      }
      return undefined
    }
  }
  return { state, guard, failure }
}
