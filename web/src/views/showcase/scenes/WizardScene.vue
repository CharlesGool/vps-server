<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import RadioField from '@/components/app/RadioField.vue'
import StepIndicator from '@/components/app/StepIndicator.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

// 场景: 多步向导. 一张整行卡片: 顶部步骤条, 中间当前步骤的字段, 底部"上一步"和"下一步"(最后一步是"完成", 主按钮); 每步校验通过才能下一步, 最后一步汇总确认.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const steps = computed(() => [t('showcase.scenes.step1'), t('showcase.scenes.step2'), t('showcase.scenes.step3')])
const step = ref(0)
const finished = ref(false)
const form = ref({ name: '', email: '', sync: 'auto' as 'auto' | 'manual' | 'schedule', timeout: 30 })
const nameError = ref('')
const syncOptions = computed(() => (['auto', 'manual', 'schedule'] as const).map((value) => ({ value, label: t(`showcase.choices.radio${value[0]!.toUpperCase()}${value.slice(1)}`) })))
const summary = computed(() => [
  { key: 'name', label: t('showcase.name'), value: form.value.name },
  { key: 'email', label: t('showcase.scenes.email'), value: form.value.email || '-' },
  { key: 'sync', label: t('showcase.choices.radio'), value: syncOptions.value.find((option) => option.value === form.value.sync)!.label },
  { key: 'timeout', label: t('showcase.choices.number'), value: `${form.value.timeout} ${t('showcase.choices.seconds')}` },
])

function next() {
  if (step.value === 0) {
    nameError.value = form.value.name.trim() ? '' : t('showcase.scenes.required')
    if (nameError.value) return
  }
  if (step.value < steps.value.length - 1) step.value++
  else finished.value = true
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesWizard')" :description="t('showcase.scenes.desc.wizard')" :trail="trail" />
    <CardForm @submit.prevent="next">
      <PageSection :cols="4" :title="t('showcase.scenes.wizardTitle')">
        <StepIndicator :steps="steps" :current="step" :label="t('showcase.scenes.steps')" />
        <AlertBanner v-if="finished" tone="success">{{ t('showcase.scenes.finished') }}</AlertBanner>
        <template v-if="step === 0">
          <FormField v-slot="field" :label="t('showcase.name')" :error="nameError" :span="6">
            <Input :id="field.id" v-model="form.name" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
          </FormField>
          <FormField v-slot="field" :label="t('showcase.scenes.email')" :span="6">
            <Input :id="field.id" v-model="form.email" type="email" />
          </FormField>
        </template>
        <template v-else-if="step === 1">
          <FormField :label="t('showcase.choices.radio')" group>
            <RadioField v-model="form.sync" :options="syncOptions" :label="t('showcase.choices.radio')" />
          </FormField>
          <FormField v-slot="field" :label="t('showcase.choices.number')">
            <NumberField :id="field.id" v-model="form.timeout" :min="0" :max="300" :step="5" :unit="t('showcase.choices.seconds')" />
          </FormField>
        </template>
        <DescriptionList v-else :items="summary" />
        <FormActions>
          <Button type="button" variant="outline" :disabled="step === 0 || finished" @click="step--">{{ t('showcase.scenes.prev') }}</Button>
          <Button type="submit" :disabled="finished">{{ step === steps.length - 1 ? t('showcase.scenes.finish') : t('showcase.scenes.next') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>
  </CardGrid>
</template>
