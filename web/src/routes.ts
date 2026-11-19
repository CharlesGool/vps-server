import { FEATURES, SHOWCASE } from './app.config'
import { FEATURE_LIST } from './features'

// 路由表只含数据, 视觉测试直接导入它来遍历全部页面; 页面组件在 router.ts 中按 view 对应.
// 组件样例: 首页加分类子页面, 只在开发和视觉测试中提供
export const SHOWCASE_PAGES = ['buttons', 'inputs', 'choices', 'data', 'feedback', 'overlays', 'layout', 'charts'] as const
export type ShowcasePage = (typeof SHOWCASE_PAGES)[number]
// 场景样例(/scenes): 常见整页的布局示例(登录, 仪表板, 设置, 列表, 长表单, 搜索结果等), 与组件样例并列
export const SHOWCASE_SCENES = ['login', 'dashboard', 'settings', 'list', 'form', 'empty', 'loading', 'error', 'forbidden', 'detail', 'edit', 'wizard', 'search'] as const
export type ShowcaseScene = (typeof SHOWCASE_SCENES)[number]
export type View = 'dashboard' | 'closed' | 'tasks' | 'restore' | 'backup' | 'files' | 'terminal' | 'visitors' | 'portfwd' | 'settings' | 'security' | 'modules' | 'logs' | 'speedtest' | 'iperf' | 'changelog' | 'login' | 'showcase' | `showcase-${ShowcasePage}` | 'showcase-scenes' | `showcase-scenes-${ShowcaseScene}`
export type PageIcon = 'home' | 'closed' | 'tasks' | 'restore' | 'backup' | 'files' | 'terminal' | 'visitors' | 'portfwd' | 'dashboard' | 'settings' | 'security' | 'modules' | 'logs' | 'speedtest' | 'iperf' | 'changelog' | 'login' | 'showcase'

export interface AppRoute {
  path: string
  name: string
  view: View
  titleKey: string
  icon: PageIcon
  // 未登录也可访问
  public?: boolean
}

// 还由 Python 生成的旧页面(迁移中): 不进入单页路由, 导航到这些路径时整页跳转. 迁移完一页就从这里删掉.
export const LEGACY_PATHS: string[] = []

export function appRoutes(features: typeof FEATURES = FEATURES, showcase = SHOWCASE): AppRoute[] {
  const routes: AppRoute[] = []
  if (features.dashboard) {
    routes.push({ path: '/', name: 'home', view: 'dashboard', titleKey: 'page.dashboard', icon: 'dashboard' })
    for (const feature of FEATURE_LIST) routes.push({ ...feature })
  } else {
    const [main] = FEATURE_LIST
    if (main) routes.push({ ...main, path: '/', name: 'home', icon: 'home' })
  }
  routes.push(
    { path: '/settings', name: 'settings', view: 'settings', titleKey: 'page.settings', icon: 'settings' },
    { path: '/settings/modules', name: 'modules', view: 'modules', titleKey: 'page.modules', icon: 'modules' },
    { path: '/backup/restore', name: 'restore', view: 'restore', titleKey: 'legacy.backup_restore_title', icon: 'restore' },
    { path: '/closed', name: 'closed', view: 'closed', titleKey: 'legacy.module_closed_title', icon: 'closed' },
    { path: '/settings/logs', name: 'logs', view: 'logs', titleKey: 'page.logs', icon: 'logs' },
    { path: '/changelog', name: 'changelog', view: 'changelog', titleKey: 'page.changelog', icon: 'changelog', public: true },
  )
  if (features.login) {
    routes.push(
      { path: '/settings/security', name: 'security', view: 'security', titleKey: 'page.security', icon: 'security' },
      { path: '/login', name: 'login', view: 'login', titleKey: 'page.login', icon: 'login', public: true },
    )
  }
  // 组件样例: 不在导航中(从设置页进入), 修改共享组件后对照它检查
  if (showcase) {
    routes.push({ path: '/showcase', name: 'showcase', view: 'showcase', titleKey: 'page.showcase', icon: 'showcase' })
    for (const page of SHOWCASE_PAGES) {
      const key = `${page[0]!.toUpperCase()}${page.slice(1)}`
      routes.push({ path: `/showcase/${page}`, name: `showcase-${page}`, view: `showcase-${page}`, titleKey: `page.showcase${key}`, icon: 'showcase' })
    }
    routes.push({ path: '/scenes', name: 'scenes', view: 'showcase-scenes', titleKey: 'page.showcaseScenes', icon: 'showcase' })
    for (const scene of SHOWCASE_SCENES) {
      const key = `${scene[0]!.toUpperCase()}${scene.slice(1)}`
      routes.push({ path: `/scenes/${scene}`, name: `scenes-${scene}`, view: `showcase-scenes-${scene}`, titleKey: `page.showcaseScenes${key}`, icon: 'showcase' })
    }
  }
  return routes.filter((route) => !LEGACY_PATHS.includes(route.path))
}
