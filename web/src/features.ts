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

export const FEATURE_LIST: Feature[] = [
  { path: '/speedtest', name: 'speedtest', view: 'speedtest', titleKey: 'legacy.speedtest', descriptionKey: 'vps.speedtest.description', icon: 'speedtest' },
  { path: '/iperf', name: 'iperf', view: 'iperf', titleKey: 'legacy.iperf_heading', descriptionKey: 'vps.iperf.description', icon: 'iperf' },
  { path: '/portfwd', name: 'portfwd', view: 'portfwd', titleKey: 'legacy.portfwd_heading', descriptionKey: 'vps.portfwd.description', icon: 'portfwd' },
  { path: '/visitors', name: 'visitors', view: 'visitors', titleKey: 'legacy.visitors', descriptionKey: 'vps.visitors.description', icon: 'visitors' },
  { path: '/terminal', name: 'terminal', view: 'terminal', titleKey: 'legacy.terminal_title', descriptionKey: 'vps.terminal.description', icon: 'terminal' },
  { path: '/files', name: 'files', view: 'files', titleKey: 'legacy.files', descriptionKey: 'vps.files.description', icon: 'files' },
  { path: '/backup', name: 'backup', view: 'backup', titleKey: 'legacy.backup', descriptionKey: 'vps.backup.description', icon: 'backup' },
  { path: '/tasks', name: 'tasks', view: 'tasks', titleKey: 'legacy.tasks', descriptionKey: 'vps.tasks.description', icon: 'tasks' },
  { path: '/tailscale', name: 'tailscale', view: 'tailscale', titleKey: 'Tailscale', descriptionKey: 'vps.tailscale.description', icon: 'tailscale' },
  { path: '/domains', name: 'domains', view: 'domains', titleKey: 'legacy.domains', descriptionKey: 'vps.domains.description', icon: 'domains' },
  { path: '/ipcert', name: 'ipcert', view: 'ipcert', titleKey: 'legacy.ipcert', descriptionKey: 'vps.ipcert.description', icon: 'ipcert' },
]
