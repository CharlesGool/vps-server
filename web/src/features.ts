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
  { path: '/monitor', name: 'monitor', view: 'monitor', titleKey: 'vps.monitor.title', descriptionKey: 'vps.monitor.description', icon: 'monitor' },
  { path: '/system', name: 'system', view: 'system', titleKey: 'vps.system.title', descriptionKey: 'vps.system.description', icon: 'system' },
  { path: '/filemanager', name: 'filemanager', view: 'filemanager', titleKey: 'vps.fm.title', descriptionKey: 'vps.fm.description', icon: 'filemanager' },
  { path: '/fleet', name: 'fleet', view: 'fleet', titleKey: 'vps.fleet.title', descriptionKey: 'vps.fleet.description', icon: 'fleet' },
  { path: '/speedtest', name: 'speedtest', view: 'speedtest', titleKey: 'console.speedtest', descriptionKey: 'vps.speedtest.description', icon: 'speedtest' },
  { path: '/iperf', name: 'iperf', view: 'iperf', titleKey: 'console.iperf_heading', descriptionKey: 'vps.iperf.description', icon: 'iperf' },
  { path: '/portfwd', name: 'portfwd', view: 'portfwd', titleKey: 'console.portfwd_heading', descriptionKey: 'vps.portfwd.description', icon: 'portfwd' },
  { path: '/visitors', name: 'visitors', view: 'visitors', titleKey: 'console.visitors', descriptionKey: 'vps.visitors.description', icon: 'visitors' },
  { path: '/terminal', name: 'terminal', view: 'terminal', titleKey: 'console.terminal_title', descriptionKey: 'vps.terminal.description', icon: 'terminal' },
  { path: '/files', name: 'files', view: 'files', titleKey: 'console.files', descriptionKey: 'vps.files.description', icon: 'files' },
  { path: '/backup', name: 'backup', view: 'backup', titleKey: 'console.backup', descriptionKey: 'vps.backup.description', icon: 'backup' },
  { path: '/tasks', name: 'tasks', view: 'tasks', titleKey: 'console.tasks', descriptionKey: 'vps.tasks.description', icon: 'tasks' },
  { path: '/tailscale', name: 'tailscale', view: 'tailscale', titleKey: 'Tailscale', descriptionKey: 'vps.tailscale.description', icon: 'tailscale' },
  { path: '/domains', name: 'domains', view: 'domains', titleKey: 'console.domains', descriptionKey: 'vps.domains.description', icon: 'domains' },
  { path: '/ipcert', name: 'ipcert', view: 'ipcert', titleKey: 'console.ipcert', descriptionKey: 'vps.ipcert.description', icon: 'ipcert' },
  { path: '/frps', name: 'frps', view: 'frps', titleKey: 'FRPS', descriptionKey: 'vps.frps.description', icon: 'frps' },
  { path: '/frpc', name: 'frpc', view: 'frpc', titleKey: 'FRPC', descriptionKey: 'vps.frpc.description', icon: 'frpc' },
  { path: '/proxy', name: 'proxy', view: 'proxy', titleKey: 'console.proxy_heading', descriptionKey: 'vps.proxy.description', icon: 'proxy' },
]
