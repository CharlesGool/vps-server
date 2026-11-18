<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import SelectMenu from '@/components/app/SelectMenu.vue'
import SettingRow from '@/components/app/SettingRow.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import { MODES, THEMES } from '@/lib/appearance'
import { LOCALES, NATIVE_NAMES } from '@/lib/i18n'

// 场景: 设置页. 一个模块一张整行卡片, 每项一行(SettingRow); 这里用本地状态, 不改变真实的外观设置.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const mode = ref<(typeof MODES)[number]>('light')
const theme = ref<string>(THEMES[0])
const language = ref<string>(LOCALES[0])
const modeOptions = computed(() => MODES.map((value) => ({ value, label: t(`mode.${value}`) })))
const themeOptions = computed(() => THEMES.map((value) => ({ value: value as string, label: t(`theme.${value}`) })))
const languageOptions = LOCALES.map((value) => ({ value: value as string, label: NATIVE_NAMES[value] }))
const notify = ref(true)
const sync = ref(false)
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesSettings')" :description="t('showcase.scenes.desc.settings')" :trail="trail" />
    <!-- 设置按模块排: 一个模块一张整行卡片, 每项一行, 左边名称和说明, 右边控件 -->
    <PageSection :cols="4" :title="t('settings.interface')">
      <SettingRow :label="t('settings.mode')" group>
        <SegmentedControl v-model="mode" :options="modeOptions" :label="t('settings.mode')" />
      </SettingRow>
      <SettingRow v-slot="row" :label="t('settings.theme')">
        <SelectMenu :id="row.id" v-model="theme" :options="themeOptions" :label="t('settings.theme')" />
      </SettingRow>
      <SettingRow :label="t('settings.language')" group>
        <SegmentedControl v-model="language" :options="languageOptions" :label="t('settings.language')" />
      </SettingRow>
    </PageSection>
    <PageSection :cols="4" :title="t('showcase.notifyTitle')">
      <SwitchField v-model="notify" :label="t('showcase.notify')" :description="t('showcase.notifyDescription')" />
      <SwitchField v-model="sync" :label="t('showcase.digest')" :description="t('showcase.digestDescription')" />
    </PageSection>
  </CardGrid>
</template>
