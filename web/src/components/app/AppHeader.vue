<script setup lang="ts">
import { Server, ScrollText, Settings, LogOut } from '@lucide/vue'
import { APP_NAME } from '@/app.config'
defineProps<{version: string; label: string; serverLabel?: string; login: boolean; items: {href: string; label: string; key: string; current?: 'page' | 'location'}[]}>()
const icons = {home: Server, changelog: ScrollText, settings: Settings, logout: LogOut}
</script>
<template>
  <header class="min-h-18 border-b border-border bg-card">
    <div class="mx-auto flex min-h-18 max-w-content flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <a href="/" data-reflow class="flex items-center gap-3 rounded-md text-lg font-semibold">
          <span class="flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground"><Server class="size-6" aria-hidden="true" /></span>
          {{ APP_NAME }}
        </a>
        <span v-if="serverLabel" data-reflow :title="serverLabel" class="max-w-48 truncate rounded-sm bg-secondary px-2 py-1 text-sm leading-tight font-semibold text-muted-foreground">{{ serverLabel }}</span>
        <a v-if="!login" href="/changelog" data-reflow class="version rounded-sm text-sm text-muted-foreground hover:text-foreground">{{ version }}</a>
      </div>
      <nav v-if="!login && items.length" :aria-label="label">
        <ul class="flex flex-wrap gap-1">
          <li v-for="item in items" :key="item.key" data-reflow>
            <a :href="item.href" :aria-current="item.current" class="flex min-h-9 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors" :class="item.current ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'">
              <component :is="icons[item.key as keyof typeof icons]" class="size-4" aria-hidden="true" />{{ item.label }}
            </a>
          </li>
        </ul>
      </nav>
    </div>
  </header>
</template>
