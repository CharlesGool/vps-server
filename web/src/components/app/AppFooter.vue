<script setup lang="ts">
import { Code, ExternalLink } from '@lucide/vue'
import { APP_NAME } from '@/app.config'

// 页面最下方的底栏: 作者主页和项目仓库.
defineProps<{ links: { href: string; label: string; key: string }[] }>()
const icons = { profile: ExternalLink, repository: Code }
</script>
<template>
  <footer class="border-t border-border bg-card">
    <div class="mx-auto flex min-h-18 max-w-content flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 md:px-6">
      <span data-reflow class="text-sm text-muted-foreground">{{ APP_NAME }}</span>
      <nav v-if="links.length" :aria-label="APP_NAME">
        <ul class="flex flex-wrap gap-1">
          <li v-for="link in links" :key="link.key" data-reflow>
            <a :href="link.href" target="_blank" rel="noopener noreferrer" class="flex min-h-9 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
              <component :is="icons[link.key as keyof typeof icons]" class="size-4" aria-hidden="true" />{{ link.label }}
            </a>
          </li>
        </ul>
      </nav>
    </div>
  </footer>
</template>
