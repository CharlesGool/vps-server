<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { APP_VERSION } from '@/app.config'
import CardGrid from '@/components/app/CardGrid.vue'
import type { Span } from '@/components/app/cardLayout'
import GroupBlock from '@/components/app/GroupBlock.vue'
import PageSection from '@/components/app/PageSection.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import { inlineSegments, loadChangelog } from '@/lib/changelog'
import type { Locale } from '@/lib/i18n'

const { t, locale } = useI18n()
const releases = computed(() => loadChangelog(locale.value as Locale))
// 版本很多, 每页 10 个, 最新的在第一页; 分页在本页最后一个版本的卡片底部
const PAGE_SIZE = 10
const page = ref(1)
watch(locale, () => (page.value = 1))
const shown = computed(() => releases.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

// 每个版本一张整行卡片, 分类(新增, 修复, 变更)在卡片里并排, 每类固定占 4 栏, 从第 1, 5, 9 栏开始, 所以各版本的分类上下对齐
const START: Span[] = [1, 5, 9]
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.changelog')" :description="t('changelog.current', { version: APP_VERSION })" />
    <PageSection v-if="!releases.length" :cols="4">
      <p class="text-muted-foreground">{{ t('changelog.empty') }}</p>
    </PageSection>
    <PageSection v-for="(release, releaseIndex) in shown" :key="release.title" as="article" :cols="4" :title="release.title">
      <GroupBlock v-for="(group, index) in release.groups" :key="group.title" :title="group.title" :span="4" :start="START[index] ?? 1">
        <!-- 条目可能含很长的路径和命令, 允许在任意处换行, 不撑宽卡片 -->
        <ul v-if="group.items.length" class="list-disc pl-6 text-sm wrap-anywhere">
          <li v-for="item in group.items" :key="item">
            <template v-for="(segment, index) in inlineSegments(item)" :key="index">
              <code v-if="segment.kind === 'code'" class="rounded-sm bg-muted px-1">{{ segment.text }}</code>
              <strong v-else-if="segment.kind === 'strong'" class="font-semibold">{{ segment.text }}</strong>
              <template v-else>{{ segment.text }}</template>
            </template>
          </li>
        </ul>
        <!-- 分类下只有段落时显示段落; 什么都没有时显示 "-" -->
        <template v-else-if="group.text.length">
          <p v-for="paragraph in group.text" :key="paragraph" class="text-sm wrap-anywhere">
            <template v-for="(segment, index) in inlineSegments(paragraph)" :key="index">
              <code v-if="segment.kind === 'code'" class="rounded-sm bg-muted px-1">{{ segment.text }}</code>
              <strong v-else-if="segment.kind === 'strong'" class="font-semibold">{{ segment.text }}</strong>
              <template v-else>{{ segment.text }}</template>
            </template>
          </p>
        </template>
        <p v-else class="text-sm text-muted-foreground">-</p>
      </GroupBlock>
      <!-- 分页放在本页最后一个版本的卡片底部 -->
      <PaginationBar v-if="releaseIndex === shown.length - 1 && releases.length > PAGE_SIZE" v-model="page" :total="releases.length" :page-size="PAGE_SIZE" />
    </PageSection>
  </CardGrid>
</template>
