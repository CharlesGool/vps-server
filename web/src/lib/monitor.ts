import { formatBytes } from './format'

// 资源监控接口(/api/monitor, 主页的 resources)的数据和格式化.
// 历史点: [开始时间(秒), CPU %, 内存 %, 下载 B/s, 上传 B/s], 没有数据的时段为 null.
export type HistoryRow = [number, number | null, number | null, number | null, number | null]

export interface Disk {
  mount: string
  device: string
  type: string
  total: number
  used: number
  free: number
  percent: number
}

export interface Monitor {
  cpu: { percent: number; cores: number; model: string }
  memory: { total: number; used: number; available: number; swapTotal: number; swapUsed: number }
  disks: Disk[]
  disk: Disk | null
  load: [number, number, number]
  uptime: number
  network: { rx: number; tx: number; interfaces: { name: string; rx: number; tx: number }[] }
  temperatures: { name: string; celsius: number }[]
  gpus: { name: string; utilization: number | null; memoryUsed: number | null; memoryTotal: number | null; celsius: number | null }[]
  chart: HistoryRow[]
  trend: HistoryRow[]
  hourAgo: { cpu: number; memory: number } | null
}

export type ResourceSummary = Pick<Monitor, 'cpu' | 'memory' | 'disk' | 'load' | 'trend' | 'hourAgo'>

export function formatRate(value: number): string {
  return `${formatBytes(value)}/s`
}

// 图表横轴: 每个时段开始的时刻(时:分, 按当前语言)
export function hourLabel(seconds: number, locale: string): string {
  return new Date(seconds * 1000).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
}

export function formatDuration(seconds: number, t: (key: string, values?: Record<string, unknown>) => string): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return days ? t('vps.monitor.daysHours', { days, hours }) : t('vps.monitor.hoursMinutes', { hours, minutes })
}
