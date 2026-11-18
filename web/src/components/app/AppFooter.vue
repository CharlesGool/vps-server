<script setup lang="ts">
import { Code, ExternalLink } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { APP_NAME, FOOTER_LINKS } from '@/app.config'

// 页面最下方的底栏: 左边项目名称, 右边作者主页和项目仓库等外部链接(app.config.ts 的 FOOTER_LINKS). 与顶栏同样的宽度和边距.
const { t } = useI18n()
const ICONS = { profile: ExternalLink, repository: Code }
</script>

<template>
  <footer data-reflow class="border-t border-border bg-card">
    <div class="mx-auto flex min-h-18 max-w-content flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3">
      <span class="text-sm text-muted-foreground">{{ APP_NAME }}</span>
      <nav v-if="FOOTER_LINKS.length" :aria-label="t('footer.label')">
        <ul class="flex flex-wrap gap-1">
          <li v-for="link in FOOTER_LINKS" :key="link.key">
            <a
              :href="link.href"
              target="_blank"
              rel="noopener noreferrer"
              class="flex h-10 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <component :is="ICONS[link.key]" class="size-4" aria-hidden="true" />
              {{ t(`footer.${link.key}`) }}
            </a>
          </li>
        </ul>
      </nav>
    </div>
  </footer>
</template>
