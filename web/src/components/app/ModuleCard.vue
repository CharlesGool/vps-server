<script setup lang="ts">
import { ChevronRight } from '@lucide/vue'
import { SwitchRoot, SwitchThumb } from 'reka-ui'
import type { Component } from 'vue'
import { type CardLayout, cardAttrs } from './cardLayout'

// 带开关的功能入口卡片: 仪表板上可以直接启停的功能(如控制台的各个模块). 和 LinkCard 一样占 1 列;
// 名称是指向功能页的链接, 右上角是立即生效的开关(开关不能放进链接里, 所以和 LinkCard 分开).
// switchLabel 是开关的无障碍名称(如"关闭测速"); 没有 switchable 时只有链接. detail 是名称下面的一行说明或提示.
// external: 在新标签页打开(如对外的公开页面).
const props = defineProps<
  {
    to: string
    title: string
    icon: Component
    detail?: string
    external?: boolean
    switchable?: boolean
    switchLabel?: string
    switchDisabled?: boolean
  } & CardLayout
>()
const enabled = defineModel<boolean>({ default: false })
</script>

<template>
  <article
    data-reflow
    data-card
    data-card-body
    data-layout="module-card"
    v-bind="cardAttrs(props)"
    class="group rounded-lg border border-border bg-card shadow-sm transition-colors hover:border-primary"
  >
    <div class="flex items-center justify-between">
      <span class="flex size-10 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
        <component :is="icon" class="size-5" aria-hidden="true" />
      </span>
      <SwitchRoot
        v-if="switchable"
        v-model="enabled"
        :disabled="switchDisabled"
        :aria-label="switchLabel"
        class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-transparent bg-input transition-colors disabled:opacity-50 data-[state=checked]:bg-primary"
      >
        <SwitchThumb class="block size-5 rounded-full bg-card shadow-sm transition-transform data-[state=checked]:translate-x-5" />
      </SwitchRoot>
    </div>
    <a v-if="external" :href="to" target="_blank" rel="noopener noreferrer" class="flex items-center justify-between gap-2 text-lg font-semibold">
      {{ title }}
      <ChevronRight class="size-5 shrink-0 text-muted-foreground group-hover:text-primary" aria-hidden="true" />
    </a>
    <RouterLink v-else :to="to" class="flex items-center justify-between gap-2 text-lg font-semibold">
      {{ title }}
      <ChevronRight class="size-5 shrink-0 text-muted-foreground group-hover:text-primary" aria-hidden="true" />
    </RouterLink>
    <p v-if="detail" class="text-sm text-muted-foreground">{{ detail }}</p>
  </article>
</template>
