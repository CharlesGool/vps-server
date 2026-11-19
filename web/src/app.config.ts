// 项目名称不翻译.
export const APP_NAME = 'vps-server'
// 在 Node 中由测试导入时没有构建常量
export const APP_VERSION = typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : 'dev'
// 组件样例页 /showcase 只在开发服务器, 视觉测试构建和测试代码(Node)中提供, 生产构建不含.
export const SHOWCASE =
  typeof __APP_VERSION__ !== 'string' || import.meta.env.DEV || import.meta.env.VITE_E2E === '1'

// 可选功能. login 必须与 Python 控制台的 VPSSRV_AUTH 一致(默认开启).
// 有两个或以上功能(src/features.ts)时 dashboard 必须为 true.
export const FEATURES = {
  login: true,
  dashboard: true,
}

// 底栏的外部链接: 作者主页和项目仓库. 复制模板后改为实际地址; 不需要时留空数组.
// text 是链接上显示的文字(不翻译); 省略时显示"作者主页", "项目仓库"这类通用名称. 通用名称总是作为提示显示.
export const FOOTER_LINKS: { key: 'profile' | 'repository'; href: string; text?: string }[] = [
  { key: 'profile', href: 'https://github.com/CharlesGool', text: 'github/CharlesGool' },
  { key: 'repository', href: 'https://github.com/CharlesGool/vps-server', text: 'github/CharlesGool/vps-server' },
]
