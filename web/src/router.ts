import { createRouter, createWebHistory, START_LOCATION, type RouteComponent } from 'vue-router'
import { FEATURES } from './app.config'
import { FEATURE_LIST } from './features'
import { hasIpRecord, loadSession, loginByIp, session } from './lib/session'
import { appRoutes, LEGACY_PATHS, type View } from './routes'

// 旧页面的占位组件: 导航前已整页跳转, 不会渲染
const LegacyPage: RouteComponent = { render: () => null }

const VIEWS: Record<View, RouteComponent | (() => Promise<RouteComponent>)> = {
  dashboard: () => import('./views/DashboardView.vue'),
  settings: () => import('./views/SettingsView.vue'),
  security: () => import('./views/SecurityView.vue'),
  modules: () => import('./views/ModulesView.vue'),
  logs: () => import('./views/LogsView.vue'),
  speedtest: () => import('./views/SpeedtestView.vue'),
  iperf: () => import('./views/IperfView.vue'),
  'portfwd': () => import('./views/PortfwdView.vue'),
  'visitors': () => import('./views/VisitorsView.vue'),
  'terminal': () => import('./views/TerminalView.vue'),
  'files': () => import('./views/FilesView.vue'),
  'backup': () => import('./views/BackupView.vue'),
  'restore': () => import('./views/RestoreView.vue'),
  'tasks': () => import('./views/TasksView.vue'),
  'closed': () => import('./views/ClosedView.vue'),
  changelog: () => import('./views/ChangelogView.vue'),
  login: () => import('./views/LoginView.vue'),
  showcase: () => import('./views/ShowcaseView.vue'),
  'showcase-buttons': () => import('./views/showcase/ButtonsView.vue'),
  'showcase-inputs': () => import('./views/showcase/InputsView.vue'),
  'showcase-choices': () => import('./views/showcase/ChoicesView.vue'),
  'showcase-data': () => import('./views/showcase/DataView.vue'),
  'showcase-feedback': () => import('./views/showcase/FeedbackView.vue'),
  'showcase-overlays': () => import('./views/showcase/OverlaysView.vue'),
  'showcase-layout': () => import('./views/showcase/LayoutView.vue'),
  'showcase-charts': () => import('./views/showcase/ChartsView.vue'),
  'showcase-scenes': () => import('./views/showcase/ScenesView.vue'),
  'showcase-scenes-login': () => import('./views/showcase/scenes/LoginScene.vue'),
  'showcase-scenes-dashboard': () => import('./views/showcase/scenes/DashboardScene.vue'),
  'showcase-scenes-settings': () => import('./views/showcase/scenes/SettingsScene.vue'),
  'showcase-scenes-list': () => import('./views/showcase/scenes/ListScene.vue'),
  'showcase-scenes-form': () => import('./views/showcase/scenes/FormScene.vue'),
  'showcase-scenes-empty': () => import('./views/showcase/scenes/EmptyScene.vue'),
  'showcase-scenes-loading': () => import('./views/showcase/scenes/LoadingScene.vue'),
  'showcase-scenes-error': () => import('./views/showcase/scenes/ErrorScene.vue'),
  'showcase-scenes-detail': () => import('./views/showcase/scenes/DetailScene.vue'),
  'showcase-scenes-edit': () => import('./views/showcase/scenes/EditScene.vue'),
  'showcase-scenes-wizard': () => import('./views/showcase/scenes/WizardScene.vue'),
  'showcase-scenes-search': () => import('./views/showcase/scenes/SearchScene.vue'),
  'showcase-scenes-forbidden': () => import('./views/showcase/scenes/ForbiddenScene.vue'),
}

if (FEATURE_LIST.length > 1 && !FEATURES.dashboard) {
  console.error('有两个或以上功能时 FEATURES.dashboard 必须为 true')
}

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    ...appRoutes().map(({ path, name, view, titleKey, icon, public: isPublic }) => ({
      path,
      name,
      component: VIEWS[view],
      meta: { titleKey, icon, public: isPublic },
    })),
    // 旧页面和其他路径交给服务器: 整页跳转
    ...[...LEGACY_PATHS, '/:pathMatch(.*)*'].map((path) => ({
      path,
      component: LegacyPage,
      meta: { legacy: true, titleKey: '', icon: 'home' as const },
    })),
  ],
})

// 启用登录时: 首次导航读取会话; 有 IP 访问记录且没有有效会话时自动发起 IP 访问.
router.beforeEach(async (to, from) => {
  if (to.meta.legacy) {
    // 首次加载就落到这里说明服务器把这个路径交给了单页但没有对应页面(如生产构建中的组件样例): 回到主页
    if (from === START_LOCATION) window.location.replace(import.meta.env.BASE_URL)
    else window.location.assign(to.fullPath)
    return false
  }
  if (!FEATURES.login) return true
  const signedIn = () => session.value?.authenticated ?? false
  if (!session.value) {
    await loadSession()
    if (!signedIn() && hasIpRecord()) await loginByIp()
  }
  const authenticated = signedIn()
  if (to.name === 'login' && authenticated) {
    const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : '/'
    return redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/'
  }
  if (to.meta.public || authenticated) return true
  return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
})
