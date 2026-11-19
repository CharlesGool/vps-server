<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import FormActions from '@/components/app/FormActions.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import SkeletonBlock from '@/components/app/SkeletonBlock.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'

// 组件样例: 反馈. 提示条(留在页面里), 进度, 加载中, 状态标签, 确认对话框(不可恢复的操作必须先确认).
const { t } = useI18n()
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
const confirmOpen = ref(false)
const deleted = ref(false)
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseFeedback')" :description="t('showcase.desc.feedback')" :trail="trail" />
    <PageSection :cols="4" :title="t('showcase.feedback.alerts')">
      <AlertBanner tone="info">{{ t('showcase.feedback.info') }}</AlertBanner>
      <AlertBanner tone="success">{{ t('showcase.feedback.success') }}</AlertBanner>
      <AlertBanner tone="warning">{{ t('showcase.feedback.warning') }}</AlertBanner>
      <AlertBanner tone="destructive" :title="t('showcase.scenes.errorTitle')">{{ t('showcase.feedback.destructive') }}</AlertBanner>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.feedback.progress')">
      <ProgressBar :label="t('showcase.feedback.uploading')" :value="64" />
      <ProgressBar variant="inline" :label="t('showcase.feedback.loading')" :value="42" text="42.4%" />
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.feedback.badges')">
      <InlineGroup>
        <StatusBadge tone="success">{{ t('showcase.feedback.running') }}</StatusBadge>
        <StatusBadge tone="warning">{{ t('showcase.feedback.pending') }}</StatusBadge>
        <StatusBadge tone="destructive">{{ t('showcase.feedback.failed') }}</StatusBadge>
        <StatusBadge>{{ t('showcase.feedback.stopped') }}</StatusBadge>
        <StatusBadge tone="info">{{ t('showcase.feedback.new') }}</StatusBadge>
      </InlineGroup>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.feedback.skeleton')">
      <SkeletonBlock :lines="4" />
      <LoadingState />
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.feedback.confirm')" :description="t('showcase.feedback.confirmText')">
      <AlertBanner :tone="deleted ? 'success' : 'warning'">{{ deleted ? t('showcase.feedback.deleted') : t('showcase.feedback.deleteText') }}</AlertBanner>
      <FormActions align="start">
        <ConfirmDialog
          v-model:open="confirmOpen"
          danger
          :title="t('showcase.feedback.deleteTitle')"
          :description="t('showcase.feedback.deleteText')"
          :confirm-label="t('showcase.feedback.deleteButton')"
          @confirm="deleted = true"
        >
          <template #trigger>
            <Button variant="destructive">{{ t('showcase.feedback.deleteButton') }}</Button>
          </template>
        </ConfirmDialog>
      </FormActions>
    </PageSection>
  </CardGrid>
</template>
