<script setup lang="ts">
import { nextTick, watch, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { APP_NAME, SHOWCASE } from './app.config'
import AppFooter from './components/app/AppFooter.vue'
import AppHeader from './components/app/AppHeader.vue'
import AppToast from './components/app/AppToast.vue'
import GridOverlay from './components/app/GridOverlay.vue'
import { mode, theme } from './lib/appearance'
import { cssDuration } from './lib/motion'
import { setPageIcon } from './lib/page-icon'
import { session } from './lib/session'

const route = useRoute()
const { t } = useI18n()

// vps-server: 设置了服务器标识时标签页标题以它开头, 同时开着几台服务器的控制台时容易分清
watchEffect(() => {
  const base = route.meta.titleKey ? `${t(route.meta.titleKey)} · ${APP_NAME}` : APP_NAME
  const label = session.value?.authenticated ? session.value.serverLabel : ''
  document.title = label ? `${label} · ${base}` : base
})

// 路由变化时立即更新标签页图标; 外观变化时等调色板过渡结束再更新.
watch(() => route.meta.icon, (icon) => setPageIcon(icon))
watch([mode, theme], async () => {
  await nextTick()
  setTimeout(() => setPageIcon(route.meta.icon), cssDuration('--duration-theme'))
})
</script>

<template>
  <!-- 顶栏, 内容区, 底栏; 内容少时底栏贴在窗口底部 -->
  <div class="flex min-h-screen flex-col">
    <AppHeader />
    <main class="mx-auto w-full max-w-content flex-1 px-4 py-4 sm:py-6">
      <RouterView />
    </main>
    <AppFooter />
  </div>
  <AppToast />
  <GridOverlay v-if="SHOWCASE" />
</template>
