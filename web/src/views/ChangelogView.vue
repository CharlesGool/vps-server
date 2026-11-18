<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { APP_VERSION } from '@/app.config'
import CardGrid from '@/components/app/CardGrid.vue'
import type { Span } from '@/components/app/cardLayout'
import GroupBlock from '@/components/app/GroupBlock.vue'
import PageSection from '@/components/app/PageSection.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import { inlineSegments, loadChangelog } from '@/lib/changelog'
import type { Locale } from '@/lib/i18n'

const { t, locale } = useI18n()
const releases = computed(() => loadChangelog(locale.value as Locale))

// 每个版本一张整行卡片, 分类(新增, 修复, 变更)在卡片里并排, 每类固定占 4 栏, 从第 1, 5, 9 栏开始, 所以各版本的分类上下对齐
const START: Span[] = [1, 5, 9]
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.changelog')" :description="t('changelog.current', { version: APP_VERSION })" />
    <PageSection v-if="!releases.length" :cols="4">
      <p class="text-muted-foreground">{{ t('changelog.empty') }}</p>
    </PageSection>
    <PageSection v-for="release in releases" :key="release.title" as="article" :cols="4" :title="release.title">
      <GroupBlock v-for="(group, index) in release.groups" :key="group.title" :title="group.title" :span="4" :start="START[index] ?? 1">
        <!-- 条目可能含很长的路径和命令, 允许在任意处换行, 不撑宽卡片 -->
        <ul class="list-disc pl-6 text-sm wrap-anywhere">
          <li v-for="item in group.items" :key="item">
            <template v-for="(segment, index) in inlineSegments(item)" :key="index">
              <code v-if="segment.kind === 'code'" class="rounded-sm bg-muted px-1">{{ segment.text }}</code>
              <strong v-else-if="segment.kind === 'strong'" class="font-semibold">{{ segment.text }}</strong>
              <template v-else>{{ segment.text }}</template>
            </template>
          </li>
        </ul>
      </GroupBlock>
    </PageSection>
  </CardGrid>
</template>
