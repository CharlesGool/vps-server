<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Gauge, HardDriveDownload, Route, UsersRound } from '@lucide/vue'
import AccordionList from '@/components/app/AccordionList.vue'
import ModuleCard from '@/components/app/ModuleCard.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

// 组件样例: 卡片布局. 卡片占整数列(cols)并可跨几行(rows), col 指定起始列(4 列布局生效);
// 卡片内的块占 span 栏, start 指定起始栏, rows 占多行. 下面的组合在 4 列布局中正好排满.
const { t } = useI18n()
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
const name = ref('')
const notes = ref('')
const type = ref('')
const agree = ref(true)
const notify = ref(false)
// 带开关的入口卡片(ModuleCard): 一行 4 张; 第二张关闭, 第三张开关不可用并带说明
const modules = ref([true, false, true, true])
const moduleCards = computed(() => [
  { key: 'speed', icon: Gauge },
  { key: 'forward', icon: Route },
  { key: 'drive', icon: HardDriveDownload, disabled: true },
  { key: 'visitors', icon: UsersRound },
])
const faq = computed(() => ['what', 'cols', 'mobile'].map((value) => ({ value, title: t(`showcase.faq.${value}.q`) })))
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseLayout')" :description="t('showcase.desc.layout')" :trail="trail" />
    <PageSection :cols="4" :title="t('showcase.layout.wide')" :description="t('showcase.layout.wideText')" />
    <!-- 跨 2 列 2 行的卡片, 旁边是两张矮卡片; 卡片里演示 span, start, rows -->
    <PageSection :cols="2" :rows="2" :title="t('showcase.layout.inner')">
      <FormField v-slot="field" :label="t('showcase.name')" :span="8">
        <Input :id="field.id" v-model="name" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.layout.type')" :span="4">
        <Input :id="field.id" v-model="type" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.notes')" :span="8" :rows="2">
        <Textarea :id="field.id" v-model="notes" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.layout.type')" :span="4">
        <Input :id="field.id" v-model="type" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.name')" :span="4">
        <Input :id="field.id" v-model="name" />
      </FormField>
      <FormActions>
        <Button>{{ t('showcase.layout.centerButton') }}</Button>
      </FormActions>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.layout.double')">
      <FormField v-slot="field" :label="t('showcase.name')" :span="6">
        <Input :id="field.id" v-model="name" />
      </FormField>
      <FormField v-slot="field" :label="t('showcase.layout.type')" :span="6">
        <Input :id="field.id" v-model="type" />
      </FormField>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.notifyTitle')">
      <SwitchField v-model="agree" :label="t('showcase.digest')" :description="t('showcase.digestDescription')" />
      <SwitchField v-model="notify" :label="t('showcase.notify')" :description="t('showcase.notifyDescription')" />
    </PageSection>
    <ModuleCard
      v-for="(card, index) in moduleCards"
      :key="card.key"
      v-model="modules[index]"
      to="/showcase/layout"
      :title="t(`showcase.layout.module.${card.key}`)"
      :icon="card.icon"
      :detail="card.disabled ? t('showcase.layout.module.notInstalled') : undefined"
      switchable
      :switch-disabled="card.disabled"
      :switch-label="t('showcase.layout.module.switch', { name: t(`showcase.layout.module.${card.key}`) })"
    />
    <!-- 折叠面板: 常见问题, 一次展开一项 -->
    <PageSection :cols="4" :title="t('showcase.faq.title')">
      <AccordionList :items="faq" default-value="what">
        <template v-for="item in faq" :key="item.value" #[item.value]>{{ t(`showcase.faq.${item.value}.a`) }}</template>
      </AccordionList>
    </PageSection>
  </CardGrid>
</template>
