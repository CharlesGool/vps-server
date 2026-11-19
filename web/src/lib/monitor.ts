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

export interface Gpu { name: string; utilization: number | null; memoryUsed: number | null; memoryTotal: number | null; celsius: number | null }
// GPU 点: [时间(秒), [[使用率 %, 显存 %, °C] 每张卡]], 15 分钟图里没有数据的分钟为 null
export type GpuRow = [number, number[][]]
export type GpuSlot = [number, number[][] | null]

export interface Monitor {
  cpu: { percent: number; cores: number; model: string }
  memory: { total: number; used: number; available: number; swapTotal: number; swapUsed: number }
  disks: Disk[]
  disk: Disk | null
  load: [number, number, number]
  uptime: number
  network: { rx: number; tx: number; interfaces: { name: string; rx: number; tx: number }[] }
  temperatures: { name: string; celsius: number }[]
  gpus: Gpu[]
  gpuLive: GpuRow[]
  gpuRecent: GpuSlot[]
  chart: HistoryRow[]
  trend: HistoryRow[]
  live: HistoryRow[]
  recent: HistoryRow[]
  hourAgo: { cpu: number; memory: number } | null
}

export type ResourceSummary = Pick<Monitor, 'cpu' | 'memory' | 'disk' | 'load' | 'trend' | 'hourAgo' | 'gpus'>

export function formatRate(value: number): string {
  return `${formatBytes(value)}/s`
}

// 实时图横轴: 时:分:秒
export function secondLabel(seconds: number, locale: string): string {
  return new Date(seconds * 1000).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
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

// 卡片和图例里用的短名称: 去掉厂商前缀(NVIDIA GeForce RTX 5090 → RTX 5090)
export function gpuName(name: string): string {
  return name.replace(/^NVIDIA\s+/i, '').replace(/^GeForce\s+/i, '') || name
}

// 每张卡一张数据卡: 值是使用率, 说明是显存和温度
export function gpuCards(gpus: Gpu[], t: (key: string, values?: Record<string, unknown>) => string, trends: number[][] = []) {
  return gpus.map((gpu, index) => ({
    key: `gpu${index}`,
    label: gpuName(gpu.name),
    value: gpu.utilization == null ? '-' : `${gpu.utilization.toFixed(0)}%`,
    delta: 0,
    deltaLabel: t('vps.monitor.gpuDetail', {
      used: gpu.memoryUsed == null ? '-' : formatBytes(gpu.memoryUsed),
      total: gpu.memoryTotal == null ? '-' : formatBytes(gpu.memoryTotal),
      celsius: gpu.celsius ?? '-',
    }),
    trend: trends[index] ?? [],
  }))
}
