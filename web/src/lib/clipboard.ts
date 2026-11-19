// 写入剪贴板; 剪贴板接口不可用(非 HTTPS)时退回到旧的复制方法.
export async function writeClipboard(text: string) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text)
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.className = 'fixed opacity-0'
  document.body.append(area)
  area.select()
  const ok = document.execCommand('copy')
  area.remove()
  if (!ok) throw new Error('copy failed')
}
