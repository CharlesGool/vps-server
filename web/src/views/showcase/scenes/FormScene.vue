<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

// 场景: 长表单. 一个表单的所有字段放在一张大卡片里(占整行, 高度由内容决定), 字段按行排: 每行从同样的栏线开始(4 + 4 + 4, 4 + 8), 左边缘上下对齐, 多行输入占整行, 提交按钮在最后.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const values = ref({ name: '', email: '', phone: '', company: '', address: '', notes: '' })
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesForm')" :description="t('showcase.scenes.desc.form')" :trail="trail" />
    <CardForm @submit.prevent>
      <PageSection :cols="4" :title="t('showcase.scenes.profile')">
        <FormField v-slot="field" :label="t('showcase.name')" :span="4">
          <Input :id="field.id" v-model="values.name" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.scenes.email')" :span="4">
          <Input :id="field.id" v-model="values.email" type="email" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.scenes.phone')" :span="4">
          <Input :id="field.id" v-model="values.phone" type="tel" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.scenes.company')" :span="4">
          <Input :id="field.id" v-model="values.company" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.scenes.address')" :span="8">
          <Input :id="field.id" v-model="values.address" />
        </FormField>
        <FormField v-slot="field" :label="t('showcase.notes')">
          <Textarea :id="field.id" v-model="values.notes" />
        </FormField>
        <FormActions>
          <Button type="button" variant="outline">{{ t('showcase.cancel') }}</Button>
          <Button type="submit">{{ t('showcase.save') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>
  </CardGrid>
</template>
