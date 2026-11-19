import { ref } from 'vue'
import { APP_VERSION, FEATURES } from '@/app.config'
import { ApiError, api, setUnauthorizedHandler } from './api'

export interface SessionInfo {
  version: string
  login: boolean
  authenticated: boolean
  method?: 'password' | 'certificate' | 'ip'
  securityUntil?: string
  // 服务器的登录方式设置: 是否允许密码登录, 证书登录, 本次连接是否出示了有效证书
  loginMethods?: { password: boolean; certificate: boolean; certificatePresented: boolean }
  // 服务器标识(设置中填写), 登录后返回
  serverLabel?: string
}

export const session = ref<SessionInfo | null>(null)

// IP 访问成功后保存记录; 有记录且没有有效会话时自动发起 IP 访问. 服务器拒绝或手动注销时清除.
const IP_RECORD_KEY = 'auth.ipAccess'

export function hasIpRecord(): boolean {
  try {
    return localStorage.getItem(IP_RECORD_KEY) === '1'
  } catch {
    return false
  }
}

function setIpRecord(value: boolean) {
  try {
    if (value) localStorage.setItem(IP_RECORD_KEY, '1')
    else localStorage.removeItem(IP_RECORD_KEY)
  } catch {
    // 存储不可用时不自动发起 IP 访问
  }
}

// 前端开关和显示的版本必须与服务器一致
function check(info: SessionInfo) {
  if (info.login !== FEATURES.login) console.error('FEATURES.login 与服务器 loginEnabled 不一致')
  if (import.meta.env.PROD && info.version !== APP_VERSION) {
    console.error(`前端版本 ${APP_VERSION} 与服务器版本 ${info.version} 不一致`)
  }
}

function signedOut() {
  if (session.value) session.value = { ...session.value, authenticated: false, method: undefined, securityUntil: undefined }
}

export async function loadSession() {
  const info = await api<SessionInfo>('session')
  check(info)
  session.value = info
}

export async function loginWithPassword(password: string) {
  session.value = await api<SessionInfo>('login', { method: 'POST', body: { password } })
}

export async function loginWithCertificate() {
  session.value = await api<SessionInfo>('login/cert', { method: 'POST' })
}

// 返回是否成功; 被拒绝时清除 IP 访问记录.
export async function loginByIp(): Promise<boolean> {
  try {
    session.value = await api<SessionInfo>('login/ip', { method: 'POST' })
    setIpRecord(true)
    return true
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) setIpRecord(false)
    else throw error
    return false
  }
}

// 注销: 结束服务器会话, 清除安全设置权限和 IP 访问记录.
export async function logout() {
  setIpRecord(false)
  await api('logout', { method: 'POST' }).catch(() => undefined)
  signedOut()
}

export async function verifyAdmin(password: string) {
  session.value = await api<SessionInfo>('security/verify', { method: 'POST', body: { password } })
}

// 任何请求返回 401 时回到登录页
export function initSession(onSignedOut: () => void) {
  setUnauthorizedHandler(() => {
    signedOut()
    onSignedOut()
  })
}
