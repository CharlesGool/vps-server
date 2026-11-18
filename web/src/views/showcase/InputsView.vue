<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import CopyField from '@/components/app/CopyField.vue'
import FileUpload from '@/components/app/FileUpload.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

// 组件样例: 文本输入. 内容多的表单拆成多张卡片, 用 CardForm 连成一个表单.
const { t } = useI18n()
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
// 只读的示例值
const endpoint = 'https://api.example.com/v1'
const name = ref('')
const password = ref('')
const notes = ref('')
const files = ref<File[]>([new File([new Uint8Array(2048)], 'report.pdf'), new File([new Uint8Array(734003)], 'photo.png')])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseInputs')" :description="t('showcase.desc.inputs')" :trail="trail" />
    <CardForm @submit.prevent>
      <PageSection :cols="4" :title="t('showcase.form')">
        <FormField v-slot="field" :label="t('showcase.name')" :help="t('showcase.nameHelp')" :span="6">
          <Input :id="field.id" v-model="name" :aria-describedby="field.describedby" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.password')" :error="t('showcase.passwordError')" :span="6">
          <PasswordInput :id="field.id" v-model="password" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.notes')">
          <Textarea :id="field.id" v-model="notes" :placeholder="t('showcase.notesPlaceholder')" />
        </FormField>
        <FormActions>
          <Button type="button" variant="outline">{{ t('showcase.cancel') }}</Button>
          <Button type="submit">{{ t('showcase.save') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>
    <!-- 只读值加复制按钮 -->
    <PageSection :cols="4" :title="t('showcase.inputs.access')" :description="t('showcase.inputs.accessText')">
      <FormField v-slot="field" :label="t('showcase.inputs.endpoint')" :span="6">
        <CopyField :id="field.id" :value="endpoint" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.inputs.apiKey')" :span="6">
        <CopyField :id="field.id" value="sk-4f9a-2c71-88e0" />
      </FormField>
    </PageSection>
    <PageSection :cols="4" :title="t('showcase.inputs.upload')">
      <FormField :label="t('showcase.inputs.uploadLabel')" group hide-label>
        <FileUpload v-model="files" multiple accept=".pdf,image/*" :max-size="5242880" :label="t('showcase.inputs.uploadLabel')" />
      </FormField>
    </PageSection>
  </CardGrid>
</template>
