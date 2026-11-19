// vps-server: 随附的 qrcode-generator(/static/third_party/qrcode/, 不经打包). 第一次用时加载.
interface QrCode {
  addData(text: string): void
  make(): void
  createSvgTag(options: { scalable: boolean }): string
}
declare global {
  interface Window {
    qrcode?: ((type: number, level: string) => QrCode) & { stringToBytes?: unknown }
  }
}
const BASE = '/static/third_party/qrcode/'
function script(name: string) {
  return new Promise<void>((resolve, reject) => {
    const element = document.createElement('script')
    element.src = BASE + name
    element.onload = () => resolve()
    element.onerror = () => reject(new Error(name))
    document.head.append(element)
  })
}
let loading: Promise<void> | undefined
// 文本生成的二维码 SVG(纠错等级 M, 可缩放)
export async function qrSvg(text: string): Promise<string> {
  loading ??= (async () => {
    if (!window.qrcode) await script('qrcode.js')
    await script('qrcode-utf8.js')
  })().catch((err) => {
    loading = undefined
    throw err
  })
  await loading
  const qr = window.qrcode!(0, 'M')
  qr.addData(text)
  qr.make()
  return qr.createSvgTag({ scalable: true })
}
