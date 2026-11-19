import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { FEATURES } from '@/app.config'
import { session } from './session'

// 页头路径的第一项: 有仪表板时是"仪表板", 否则是"主页"; 启用登录而未登录时(公开页面如变更日志)是"登录", 指向登录页.
export function useHomeCrumb() {
  const { t } = useI18n()
  return computed(() => {
    if (FEATURES.login && !session.value?.authenticated) return { to: '/login', label: t('page.login') }
    return { to: '/', label: t(FEATURES.dashboard ? 'page.dashboard' : 'nav.home') }
  })
}
