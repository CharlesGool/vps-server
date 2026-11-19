import type { PageIcon, View } from './routes'

// 面向用户的功能列表. 启用仪表板时每项是单页里的一个功能页; 主页的模块卡片(ModuleCard)由服务器的 /api/dashboard 给出.
// view 对应 router.ts 中的页面组件, icon 对应 lib/page-icon.ts 中的页面符号.
// vps-server 迁移期间(见 doc/LOG.md 决策 2026-11-18)功能页还由服务器生成, 迁移一页就在这里加一项.
export interface Feature {
  path: string
  name: string
  view: View
  titleKey: string
  descriptionKey: string
  icon: PageIcon
}

export const FEATURE_LIST: Feature[] = []
