<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import ProgressBar from '@/components/app/ProgressBar.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'

// 场景: 详情页. 只读信息用描述列表(DescriptionList), 状态用标签, 操作放在卡片最后一行: 更多操作菜单在左, 主操作"编辑"在最右.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const items = computed(() => [
  { key: 'name', label: t('showcase.table.name'), value: 'host-1' },
  { key: 'status', label: t('showcase.table.status') },
  { key: 'address', label: t('showcase.table.address'), value: '192.168.1.20', mono: true, copyable: true },
  { key: 'created', label: t('showcase.scenes.createdAt'), value: '2026-05-12 09:30' },
])
const menu = computed(() => [
  { key: 'duplicate', label: t('showcase.overlays.duplicate') },
  { key: 'remove', label: t('showcase.overlays.remove'), danger: true },
])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesDetail')" :description="t('showcase.scenes.desc.detail')" :trail="trail" />
    <PageSection :cols="2" :title="t('showcase.scenes.basicInfo')">
      <DescriptionList :items="items">
        <template #value-status>
          <StatusBadge tone="success">{{ t('showcase.feedback.running') }}</StatusBadge>
        </template>
      </DescriptionList>
      <FormActions>
        <ActionMenu :label="t('component.moreActions')" :items="menu" />
        <Button as-child>
          <RouterLink to="/scenes/edit">{{ t('showcase.scenes.edit') }}</RouterLink>
        </Button>
      </FormActions>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.scenes.runtime')">
      <ProgressBar :label="t('showcase.scenes.cpu')" :value="42" />
      <ProgressBar :label="t('showcase.scenes.memory')" :value="86" />
      <AlertBanner tone="warning">{{ t('showcase.feedback.warning') }}</AlertBanner>
    </PageSection>
  </CardGrid>
</template>
