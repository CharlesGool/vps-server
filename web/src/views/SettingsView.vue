<script setup lang="ts">
import { ShieldCheck } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { FEATURES } from '@/app.config'
import CardGrid from '@/components/app/CardGrid.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import FormActions from '@/components/app/FormActions.vue'
import PageSection from '@/components/app/PageSection.vue'
import SettingRow from '@/components/app/SettingRow.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import ThemeSelect from '@/components/app/ThemeSelect.vue'
import { Button } from '@/components/ui/button'
import { MODES, mode } from '@/lib/appearance'
import { type Locale, LOCALES, NATIVE_NAMES } from '@/lib/i18n'

const { t, locale } = useI18n()

const modeOptions = computed(() => MODES.map((value) => ({ value, label: t(`mode.${value}`) })))
const localeOptions = LOCALES.map((value) => ({ value, label: NATIVE_NAMES[value] }))
const currentLocale = computed({
  get: () => locale.value as Locale,
  set: (value: Locale) => (locale.value = value),
})
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.settings')" />
    <!-- 设置按模块排: 一个模块一张整行卡片, 每项一行(左边名称, 右边控件) -->
    <PageSection :cols="4" :title="t('settings.interface')">
      <SettingRow :label="t('settings.mode')" group>
        <SegmentedControl v-model="mode" :options="modeOptions" :label="t('settings.mode')" />
      </SettingRow>
      <SettingRow :label="t('settings.theme')" group>
        <ThemeSelect :label="t('settings.theme')" />
      </SettingRow>
      <SettingRow :label="t('settings.language')" group>
        <SegmentedControl v-model="currentLocale" :options="localeOptions" :label="t('settings.language')" />
      </SettingRow>
    </PageSection>
    <!-- 只有"进入安全设置"启动管理员验证 -->
    <PageSection v-if="FEATURES.login" :cols="4" :title="t('settings.security')">
      <SettingRow :label="t('settings.enterSecurity')" :description="t('settings.securityDescription')" group>
        <FormActions>
          <Button as-child variant="outline">
            <RouterLink to="/settings/security">
              <ShieldCheck aria-hidden="true" />
              {{ t('settings.enterSecurity') }}
            </RouterLink>
          </Button>
        </FormActions>
      </SettingRow>
    </PageSection>
  </CardGrid>
</template>
