<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import CheckboxField from '@/components/app/CheckboxField.vue'
import DateTimePicker from '@/components/app/DateTimePicker.vue'
import FormField from '@/components/app/FormField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import RangeSlider from '@/components/app/RangeSlider.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import ComboboxField from '@/components/app/ComboboxField.vue'
import NumberField from '@/components/app/NumberField.vue'
import RadioField from '@/components/app/RadioField.vue'
import SelectMenu from '@/components/app/SelectMenu.vue'
import TagsField from '@/components/app/TagsField.vue'
import SettingRow from '@/components/app/SettingRow.vue'
import SwitchField from '@/components/app/SwitchField.vue'

// 组件样例: 选择. 并排的字段用 span(6 + 6).
const { t } = useI18n()
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
const size = ref<'s' | 'm' | 'l'>('m')
const region = ref<string>()
const agree = ref(true)
const notify = ref(false)
const date = ref('2026-05-12')
const time = ref('09:30')
const dateTime = ref('2026-05-12T18:00')
const level = ref(60)
const sync = ref<'auto' | 'manual' | 'schedule'>('auto')
const comboRegion = ref<string>()
const multiRegions = ref<string[]>(['north', 'east'])
const tags = ref(['alpha', 'beta'])
const timeout = ref(30)
const syncOptions = computed(() => (['auto', 'manual', 'schedule'] as const).map((value) => ({ value, label: t(`showcase.choices.radio${value[0]!.toUpperCase()}${value.slice(1)}`), description: t(`showcase.choices.radio${value[0]!.toUpperCase()}${value.slice(1)}Text`) })))
const sizes = computed(() => (['s', 'm', 'l'] as const).map((value) => ({ value, label: t(`showcase.size.${value}`) })))
const regions = computed(() =>
  ['north', 'south', 'east', 'west', 'center', 'overseas'].map((value) => ({ value, label: t(`showcase.region.${value}`) })),
)
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseChoices')" :description="t('showcase.desc.choices')" :trail="trail" />
    <PageSection :cols="4" :title="t('showcase.dateTimeInputs')">
      <FormField v-slot="field" :label="t('showcase.date')" :span="4">
        <DateTimePicker :id="field.id" v-model="date" :label="t('showcase.date')" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.time')" :span="4">
        <DateTimePicker :id="field.id" v-model="time" mode="time" :label="t('showcase.time')" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.dateTime')" :span="4">
        <DateTimePicker :id="field.id" v-model="dateTime" mode="datetime" :label="t('showcase.dateTime')" />
      </FormField>
    </PageSection>
    <!-- 表单样式: 标签在上的字段和勾选框 -->
    <PageSection :cols="2" :title="t('showcase.form')">
      <FormField :label="t('showcase.sizeLabel')" group>
        <SegmentedControl v-model="size" :options="sizes" :label="t('showcase.sizeLabel')" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.regionLabel')">
        <SelectMenu
          :id="field.id"
          v-model="region"
          :options="regions"
          :label="t('showcase.regionLabel')"
          :placeholder="t('showcase.regionPlaceholder')"
        />
      </FormField>
      <!-- 协议勾选: 没有说明, 协议正文是标签里的链接(复制模板后指向实际的条款页) -->
      <CheckboxField v-model="agree" :label="`${t('showcase.agreePrefix')}${t('showcase.terms')}`">
        <template #label>
          {{ t('showcase.agreePrefix') }}<RouterLink to="/scenes/empty" class="text-primary underline">{{ t('showcase.terms') }}</RouterLink>
        </template>
      </CheckboxField>
    </PageSection>
    <!-- 设置行样式: 左边名称, 右边开关或滑块 -->
    <PageSection :cols="2" :title="t('page.showcaseChoices')">
      <SwitchField v-model="notify" :label="t('showcase.notify')" :description="t('showcase.notifyDescription')" />
      <SettingRow :label="t('showcase.level')" group>
        <RangeSlider v-model="level" :label="t('showcase.level')" />
      </SettingRow>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.choices.group')">
      <FormField :label="t('showcase.choices.radio')" group>
        <RadioField v-model="sync" :options="syncOptions" :label="t('showcase.choices.radio')" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.choices.combobox')">
        <ComboboxField :id="field.id" v-model="comboRegion" :options="regions" :label="t('showcase.choices.combobox')" :placeholder="t('showcase.choices.comboboxPlaceholder')" />
      </FormField>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.choices.group2')">
      <FormField v-slot="field" :label="t('showcase.choices.multi')">
        <ComboboxField :id="field.id" v-model="multiRegions" multiple :options="regions" :label="t('showcase.choices.multi')" :placeholder="t('showcase.choices.comboboxPlaceholder')" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.choices.tags')">
        <TagsField :id="field.id" v-model="tags" :placeholder="t('showcase.choices.tagsPlaceholder')" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.choices.number')">
        <NumberField :id="field.id" v-model="timeout" :min="0" :max="300" :step="5" :unit="t('showcase.choices.seconds')" />
      </FormField>
    </PageSection>
  </CardGrid>
</template>
