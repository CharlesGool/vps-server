<script setup lang="ts">
import VersionLink from '@/components/app/VersionLink.vue'
import { House, LogOut, Menu, ScrollText, Settings } from '@lucide/vue'
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuRoot, DropdownMenuTrigger } from 'reka-ui'
import { Button } from '@/components/ui/button'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { APP_NAME, FEATURES } from '@/app.config'
import { logout, session } from '@/lib/session'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// 登录页和未登录时只显示项目名称; 已登录或无登录时显示应用导航.
const signedIn = computed(() => !FEATURES.login || (session.value?.authenticated ?? false))
const bare = computed(() => route.name === 'login' || !signedIn.value)

const items = computed(() => [
  ...(FEATURES.dashboard ? [{ to: '/', label: 'nav.home', icon: House }] : []),
  { to: '/changelog', label: 'nav.changelog', icon: ScrollText },
  { to: '/settings', label: 'nav.settings', icon: Settings },
])

// 当前页为 page; 设置的子页面为 location
function current(to: string) {
  if (route.path === to) return 'page'
  if (to !== '/' && route.path.startsWith(`${to}/`)) return 'location'
  return undefined
}

async function signOut() {
  await logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <header data-reflow class="border-b border-border bg-card">
    <div
      class="mx-auto flex min-h-18 max-w-content flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3"
    >
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <!-- 项目名称用主题色; 不显示项目标志(项目决策 2026-10-07, 见 doc/LOG.md) -->
        <RouterLink to="/" class="flex min-h-10 items-center gap-3 rounded-md text-lg font-semibold text-primary">
          {{ APP_NAME }}
        </RouterLink>
        <VersionLink v-if="!bare" />
      </div>
      <nav v-if="!bare" :aria-label="t('nav.label')" class="hidden sm:block">
        <ul class="flex flex-wrap items-center gap-1">
          <li v-for="item in items" :key="item.to">
            <RouterLink
              :to="item.to"
              class="flex h-10 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors"
              :class="
                current(item.to)
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              "
              :aria-current="current(item.to)"
            >
              <component :is="item.icon" class="size-4" aria-hidden="true" />
              {{ t(item.label) }}
            </RouterLink>
          </li>
          <li v-if="FEATURES.login">
            <button
              type="button"
              class="flex h-10 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              @click="signOut"
            >
              <LogOut class="size-4" aria-hidden="true" />
              {{ t('nav.logout') }}
            </button>
          </li>
        </ul>
      </nav>
      <!-- 窄屏(640 px 以下): 导航收进一个菜单按钮, 顶栏保持一行 -->
      <DropdownMenuRoot v-if="!bare">
        <DropdownMenuTrigger as-child>
          <Button variant="outline" size="icon-sm" class="w-8 sm:hidden" :aria-label="t('nav.menu')"><Menu aria-hidden="true" /></Button>
        </DropdownMenuTrigger>
        <DropdownMenuPortal>
          <DropdownMenuContent align="end" :side-offset="4" class="z-50 min-w-40 overflow-hidden rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md">
            <DropdownMenuItem v-for="item in items" :key="item.to" as-child>
              <RouterLink :to="item.to" :aria-current="current(item.to)" class="flex h-10 items-center gap-2 rounded-sm px-2 text-sm outline-none data-highlighted:bg-accent data-highlighted:text-accent-foreground" :class="current(item.to) && 'font-semibold text-primary'">
                <component :is="item.icon" class="size-4" aria-hidden="true" />
                {{ t(item.label) }}
              </RouterLink>
            </DropdownMenuItem>
            <DropdownMenuItem v-if="FEATURES.login" class="flex h-10 cursor-pointer items-center gap-2 rounded-sm px-2 text-sm outline-none data-highlighted:bg-accent data-highlighted:text-accent-foreground" @select="signOut">
              <LogOut class="size-4" aria-hidden="true" />
              {{ t('nav.logout') }}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenuPortal>
      </DropdownMenuRoot>
    </div>
  </header>
</template>
