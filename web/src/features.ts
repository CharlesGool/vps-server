// 面向用户的功能列表. 启用仪表板时每项显示为一张入口卡片; 未启用时第一项作为主页.
// view 对应 router.ts 中的页面组件, icon 对应 lib/page-icon.ts 中的页面符号.
export interface Feature {
  path: string
  name: string
  view: 'example'
  titleKey: string
  descriptionKey: string
  icon: 'example'
}

export const FEATURE_LIST: Feature[] = [
  {
    path: '/example',
    name: 'example',
    view: 'example',
    titleKey: 'page.example',
    descriptionKey: 'example.description',
    icon: 'example',
  },
]
