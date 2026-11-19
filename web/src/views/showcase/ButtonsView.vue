<script setup lang="ts">
import { Plus, Trash2 } from '@lucide/vue'
import { computed } from 'vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import FormActions from '@/components/app/FormActions.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import { Button } from '@/components/ui/button'

// 组件样例: 按钮. 一行 1 到 4 个按钮, 按数量等分所占的栏.
const { t } = useI18n()
const confirm = ref(false)
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseButtons')" :description="t('showcase.desc.buttons')" :trail="trail" />
    <!-- 按钮宽度随文字; 一张卡片只有一个主按钮 -->
    <PageSection :cols="4" :title="t('showcase.buttons')">
      <FormActions align="start">
        <Button>{{ t('showcase.primary') }}</Button>
        <Button variant="secondary">{{ t('showcase.secondary') }}</Button>
        <Button variant="outline"><Plus aria-hidden="true" />{{ t('showcase.add') }}</Button>
        <!-- 危险按钮只用来触发确认对话框 -->
        <ConfirmDialog v-model:open="confirm" danger :title="t('showcase.feedback.deleteTitle')" :description="t('showcase.feedback.deleteText')" :confirm-label="t('showcase.delete')">
          <template #trigger>
            <Button variant="destructive"><Trash2 aria-hidden="true" />{{ t('showcase.delete') }}</Button>
          </template>
        </ConfirmDialog>
        <Button variant="outline" disabled>{{ t('showcase.disabled') }}</Button>
      </FormActions>
    </PageSection>
  </CardGrid>
</template>
