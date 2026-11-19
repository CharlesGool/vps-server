<script setup lang="ts">
import { Plus } from '@lucide/vue'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import SideDrawer from '@/components/app/SideDrawer.vue'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { showToast } from '@/lib/toast'

// 组件样例: 浮层和反馈. 对话框内容同卡片的 12 栏栅格.
const { t } = useI18n()
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
const dialog = ref(false)
const name = ref('')
const drawer = ref(false)
const notes = ref('')
const details = computed(() => [
  { key: 'name', label: t('showcase.table.name'), value: 'host-1' },
  { key: 'address', label: t('showcase.table.address'), value: '192.168.1.20', mono: true, copyable: true },
  { key: 'created', label: t('showcase.scenes.createdAt'), value: '2026-05-12 09:30' },
])
const removing = ref(false)
const removed = ref(false)
const menuItems = computed(() => [
  { key: 'edit', label: t('showcase.overlays.edit') },
  { key: 'duplicate', label: t('showcase.overlays.duplicate') },
  { key: 'remove', label: t('showcase.overlays.remove'), danger: true },
])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseOverlays')" :description="t('showcase.desc.overlays')" :trail="trail" />
    <PageSection :cols="4" :title="t('page.showcaseOverlays')" :description="t('example.toastDescription')">
      <AlertBanner v-if="removed" tone="success">{{ t('showcase.feedback.deleted') }}</AlertBanner>
      <FormActions align="start">
        <AppDialog v-model:open="dialog" :title="t('showcase.dialogTitle')" :description="t('showcase.dialogDescription')">
          <template #trigger>
            <Button variant="outline"><Plus aria-hidden="true" />{{ t('showcase.add') }}</Button>
          </template>
          <FormField v-slot="field" :label="t('showcase.name')">
            <Input :id="field.id" v-model="name" />
          </FormField>
          <template #footer>
            <Button variant="outline" @click="dialog = false">{{ t('showcase.cancel') }}</Button>
            <Button @click="dialog = false">{{ t('showcase.save') }}</Button>
          </template>
        </AppDialog>
        <Button variant="outline" @click="showToast(t('example.toastFailed'), 'destructive', t('example.toastFailedDetail'))">
          {{ t('example.toastErrorButton') }}
        </Button>
        <SideDrawer v-model:open="drawer" :title="t('showcase.drawer.title')" :description="t('showcase.drawer.description')">
          <template #trigger>
            <Button variant="outline">{{ t('showcase.drawer.open') }}</Button>
          </template>
          <DescriptionList :items="details" />
          <FormField v-slot="field" :label="t('showcase.notes')">
            <Textarea :id="field.id" v-model="notes" />
          </FormField>
          <template #footer>
            <Button variant="outline" @click="drawer = false">{{ t('showcase.cancel') }}</Button>
            <Button @click="drawer = false">{{ t('showcase.save') }}</Button>
          </template>
        </SideDrawer>
        <ActionMenu :label="t('component.moreActions')" :items="menuItems" @select="(key) => key === 'remove' && (removing = true)" />
        <Button @click="showToast(t('example.toastSaved'), 'success', t('example.toastSavedDetail'))">{{ t('example.toastButton') }}</Button>
      </FormActions>
      <ConfirmDialog
        v-model:open="removing"
        danger
        :title="t('showcase.feedback.deleteTitle')"
        :description="t('showcase.feedback.deleteText')"
        :confirm-label="t('showcase.overlays.remove')"
        @confirm="removed = true"
      />
    </PageSection>
  </CardGrid>
</template>
