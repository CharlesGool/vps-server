// 字节数按 1024 进位显示, 与控制台服务器的 total_meter.format_bytes 一致: B 取整, 其余保留两位小数.
export function formatBytes(value: number): string {
  let size = value
  for (const unit of ['B', 'KiB', 'MiB', 'GiB', 'TiB']) {
    if (size < 1024 || unit === 'TiB') return unit === 'B' ? `${Math.round(size)} ${unit}` : `${size.toFixed(2)} ${unit}`
    size /= 1024
  }
  return `${value} B`
}
