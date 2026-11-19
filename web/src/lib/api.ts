// 同源 API 请求; 路径相对部署基础路径, 如 api('session').
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    // 错误响应的其他字段, 如 too_many_attempts 的 retryAfter(秒)
    readonly data: Record<string, unknown> = {},
  ) {
    super(code)
  }
}

// 会话失效(401)时调用, 由 session.ts 设置
let onUnauthorized: (() => void) | undefined
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}api/${path}`, {
    method: init.method ?? 'GET',
    credentials: 'same-origin',
    headers: init.body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  })
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const code = typeof data.error === 'string' ? data.error : 'request_failed'
    if (response.status === 401 && code === 'unauthenticated') onUnauthorized?.()
    // vps-server: 功能已被关闭时服务器给出说明页的地址(由服务器生成, 迁移期间整页跳转)
    if (code === 'feature_closed' && typeof data.url === 'string' && data.url.startsWith('/')) window.location.replace(data.url)
    throw new ApiError(response.status, code, data)
  }
  return data as T
}

// 会话失效(401 unauthenticated)时 session.ts 已经转到登录页, 功能已关闭(feature_closed)时已经转到说明页: 页面的请求不必再报错
export function isSignedOut(error: unknown): boolean {
  return error instanceof ApiError && ((error.status === 401 && error.code === 'unauthenticated') || error.code === 'feature_closed')
}
