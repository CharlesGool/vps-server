<script setup lang="ts">
import { ChevronRight, Settings } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RouteLocationRaw } from 'vue-router'
import { Button } from '@/components/ui/button'
import { useHomeCrumb } from '@/lib/navigation'

// 页头: 页面第一行, 不是卡片, 直接放在页面背景上, 占满一行. 第一行是路径和标题合一: 主页 > 上级页面(小号链接, 就是返回上级的方式) > 当前页(放大的标题 h1);
// 当前页名称只出现一次, 倒数第二项就是上一级. 第二行是说明(可选).
// trail 是主页和当前页之间的上级页面, 从主页向下写; root 页面(主页本身)没有路径. 功能自己的设置按钮(settings-to)在标题右边.
const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    trail?: { to: RouteLocationRaw; label: string }[]
    root?: boolean
    settingsTo?: RouteLocationRaw
  }>(),
  { trail: () => [] },
)

const { t } = useI18n()
const home = useHomeCrumb()
const crumbs = computed(() => [home.value as { to: RouteLocationRaw; label: string }, ...props.trail])
</script>

<template>
  <div data-reflow data-layout="page-header" class="flex flex-col gap-1">
    <!-- 路径和标题合一: 上级页面是小号链接, 当前页是放大的标题(h1), 所以倒数第二项就是上一级, 当前页名称只出现一次 -->
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="flex flex-wrap items-center gap-x-2">
        <nav v-if="!root" :aria-label="t('nav.path')">
          <ol class="flex flex-wrap items-center gap-1">
            <li v-for="crumb in crumbs" :key="String(crumb.label)" class="flex items-center gap-1">
              <RouterLink :to="crumb.to" class="flex h-6 min-w-6 items-center rounded-sm text-muted-foreground hover:text-foreground">{{ crumb.label }}</RouterLink>
              <ChevronRight class="size-4 text-muted-foreground" aria-hidden="true" />
            </li>
          </ol>
        </nav>
        <h1 class="text-2xl font-semibold">{{ title }}</h1>
      </div>
      <Button v-if="settingsTo" as-child variant="outline" size="sm">
        <RouterLink :to="settingsTo">
          <Settings aria-hidden="true" />
          {{ t('action.settings') }}
        </RouterLink>
      </Button>
    </div>
    <p v-if="description" class="text-muted-foreground">{{ description }}</p>
  </div>
</template>
