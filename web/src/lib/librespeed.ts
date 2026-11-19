// vps-server: 随附的 LibreSpeed 测速引擎(/static/speedtest.js, 不经打包). 第一次用时加载一次.
// 引擎自己创建 Worker("speedtest_worker.js"), 路径相对当前页面(/speedtest), 服务器在 /speedtest_worker.js 提供.
export interface SpeedtestUpdate {
  testState: number
  dlStatus: string
  ulStatus: string
  pingStatus: string
  jitterStatus: string
}
export interface Speedtest {
  setParameter(name: string, value: unknown): void
  onupdate: (data: SpeedtestUpdate) => void
  onend: (aborted: boolean) => void
  start(): void
  abort(): void
}
declare global {
  interface Window {
    Speedtest?: new () => Speedtest
  }
}

let loading: Promise<new () => Speedtest> | undefined
export function loadSpeedtest(): Promise<new () => Speedtest> {
  loading ??= new Promise((resolve, reject) => {
    if (window.Speedtest) return resolve(window.Speedtest)
    const script = document.createElement('script')
    script.src = '/static/speedtest.js'
    script.onload = () => (window.Speedtest ? resolve(window.Speedtest) : reject(new Error('speedtest.js')))
    script.onerror = () => {
      loading = undefined
      reject(new Error('speedtest.js'))
    }
    document.head.append(script)
  })
  return loading
}
