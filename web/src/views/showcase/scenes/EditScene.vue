<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useUnsavedGuard } from '@/lib/unsaved'

// 场景: 编辑页. 有未保存的修改时顶部显示提示条, "保存"和"取消"才可用; 保存后提示"已保存"; 带着未保存的修改离开(点路径, 菜单, 浏览器后退)要先确认.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const saved = ref({ name: 'host-1', address: '192.168.1.20', notes: '' })
const form = reactive({ ...saved.value })
const dirty = computed(() => JSON.stringify(form) !== JSON.stringify(saved.value))
const error = ref('')
const done = ref(false)
const guard = useUnsavedGuard(dirty)

function save() {
  error.value = form.name.trim() ? '' : t('showcase.scenes.required')
  if (error.value) return
  saved.value = { ...form }
  done.value = true
}
function reset() {
  Object.assign(form, saved.value)
  error.value = ''
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesEdit')" :description="t('showcase.scenes.desc.edit')" :trail="trail" />
    <CardForm @submit.prevent="save">
      <PageSection :cols="4" :title="t('showcase.scenes.basicInfo')">
        <AlertBanner v-if="dirty" tone="warning">{{ t('showcase.scenes.unsaved') }}</AlertBanner>
        <AlertBanner v-else-if="done" tone="success">{{ t('showcase.scenes.saved') }}</AlertBanner>
        <FormField v-slot="field" :label="t('showcase.name')" :error="error" :span="6">
          <Input :id="field.id" v-model="form.name" :aria-invalid="field.invalid" :aria-describedby="field.describedby" @input="done = false" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.scenes.address')" :span="6">
          <Input :id="field.id" v-model="form.address" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.notes')">
          <Textarea :id="field.id" v-model="form.notes" />
        </FormField>
        <FormActions>
          <Button type="button" variant="outline" :disabled="!dirty" @click="reset">{{ t('showcase.cancel') }}</Button>
          <Button type="submit" :disabled="!dirty">{{ t('showcase.save') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>
    <ConfirmDialog
      v-model:open="guard.open.value"
      danger
      :title="t('showcase.scenes.discardTitle')"
      :description="t('showcase.scenes.discardText')"
      :confirm-label="t('showcase.scenes.discardButton')"
      @confirm="guard.confirm"
    />
  </CardGrid>
</template>
