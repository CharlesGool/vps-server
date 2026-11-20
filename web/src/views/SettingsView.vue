<script setup lang="ts">
import { Activity, Package, ShieldCheck } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import SettingRow from '@/components/app/SettingRow.vue'
import ThemeSelect from '@/components/app/ThemeSelect.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, isSignedOut } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { MODES, mode } from '@/lib/appearance'
import { type Locale, LOCALES, NATIVE_NAMES } from '@/lib/i18n'
import { session } from '@/lib/session'
import { showToast } from '@/lib/toast'

interface Settings {
  serverLabel: string
  consolePort: number
  consolePortJob: { state: string; reason: string } | null
}

const { t, locale } = useI18n()

const modeOptions = computed(() => MODES.map((value) => ({ value, label: t(`mode.${value}`) })))
const localeOptions = LOCALES.map((value) => ({ value, label: NATIVE_NAMES[value] }))
const currentLocale = computed({
  get: () => locale.value as Locale,
  set: (value: Locale) => (locale.value = value),
})

const loaded = ref(false)
const label = ref('')
const labelError = ref('')
const labelBusy = ref(false)
const port = ref(0)
const currentPort = ref(0)
const portError = ref('')
const portBusy = ref(false)
const portJobFailed = ref('')
// 端口修改已开始: 当前端口即将停止, 给出新旧两个地址
const moved = ref<{ url: string; oldUrl: string }>()

onMounted(async () => {
  try {
    const data = await api<Settings>('settings')
    label.value = data.serverLabel
    port.value = currentPort.value = data.consolePort
    if (data.consolePortJob?.state === 'failed') portJobFailed.value = data.consolePortJob.reason
    loaded.value = true
  } catch (err) {
    if (!isSignedOut(err)) showToast(errorText(err), 'destructive')
  }
})

const ERRORS: Record<string, string> = {
  server_label_invalid: 'vps.settings.labelInvalid',
  server_label_error: 'vps.settings.labelError',
  console_port_invalid: 'vps.settings.portInvalid',
  console_port_error: 'vps.settings.portError',
}
const message = (err: unknown) =>
  errorText(err, { codes: (code) => (ERRORS[code] ? t(ERRORS[code]!) : undefined), labels: { label: t('vps.settings.label'), port: t('vps.settings.port') } })

async function saveLabel() {
  if (labelBusy.value) return
  labelBusy.value = true
  labelError.value = ''
  try {
    const data = await api<{ serverLabel: string }>('settings/server-label', { method: 'PUT', body: { label: label.value } })
    label.value = data.serverLabel
    if (session.value) session.value = { ...session.value, serverLabel: data.serverLabel }
    showToast(t('vps.settings.labelSaved'), 'success')
  } catch (err) {
    labelError.value = message(err)
  } finally {
    labelBusy.value = false
  }
}

async function changePort() {
  if (portBusy.value) return
  portBusy.value = true
  portError.value = ''
  try {
    moved.value = await api<{ url: string; oldUrl: string }>('settings/console-port', { method: 'POST', body: { port: port.value } })
  } catch (err) {
    portError.value = message(err)
  } finally {
    portBusy.value = false
  }
}
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
    <!-- 服务器标识和控制台端口各是一个表单, 并排两张半行卡片 -->
    <CardForm @submit.prevent="saveLabel">
      <PageSection :cols="2" :title="t('vps.settings.identity')" :description="t('vps.settings.identityDescription')">
        <FormField v-slot="field" :label="t('vps.settings.label')" :error="labelError">
          <Input :id="field.id" v-model="label" maxlength="40" autocomplete="off" :disabled="!loaded" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
        </FormField>
        <FormActions>
          <Button type="submit" :disabled="!loaded || labelBusy">{{ t('vps.settings.labelSave') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>
    <CardForm @submit.prevent="changePort">
      <PageSection :cols="2" :title="t('vps.settings.consolePort')" :description="t('vps.settings.consolePortDescription')">
        <AlertBanner v-if="portJobFailed" tone="destructive" :title="t('vps.settings.portError')">{{ portJobFailed }}</AlertBanner>
        <AlertBanner v-if="moved" tone="warning" :title="t('vps.settings.portStarted')">
          <a :href="moved.url" class="font-medium text-primary underline">{{ t('vps.settings.portOpenNew') }}</a>
          ·
          <a :href="moved.oldUrl" class="text-primary underline">{{ t('vps.settings.portReturnOld') }}</a>
        </AlertBanner>
        <FormField v-slot="field" :label="t('vps.settings.port')" :error="portError">
          <NumberField :id="field.id" v-model="port" :min="1024" :max="65535" :grouping="false" :disabled="!loaded" />
        </FormField>
        <FormActions>
          <Button type="submit" :disabled="!loaded || portBusy || port === currentPort">{{ t('vps.settings.portSave') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>
    <PageSection :cols="4" :title="t('vps.settings.manage')">
      <SettingRow :label="t('vps.settings.modules')" :description="t('vps.settings.modulesDescription')" group>
        <FormActions>
          <Button as-child variant="outline">
            <RouterLink to="/settings/modules"><Package aria-hidden="true" />{{ t('vps.settings.openModules') }}</RouterLink>
          </Button>
        </FormActions>
      </SettingRow>
      <SettingRow :label="t('vps.settings.logs')" :description="t('vps.settings.logsDescription')" group>
        <FormActions>
          <Button as-child variant="outline">
            <RouterLink to="/settings/logs"><Activity aria-hidden="true" />{{ t('vps.settings.openLogs') }}</RouterLink>
          </Button>
        </FormActions>
      </SettingRow>
    </PageSection>
    <!-- 只有"进入安全设置"启动管理员验证 -->
    <PageSection :cols="4" :title="t('settings.security')">
      <SettingRow :label="t('settings.enterSecurity')" :description="t('vps.settings.securityDescription')" group>
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
