<script setup lang="ts">
import { Lock } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import { type Locale, LOCALES, NATIVE_NAMES } from '@/lib/i18n'
import { blockAttrs } from './cardLayout'
import CardForm from './CardForm.vue'
import FormActions from './FormActions.vue'
import FormField from './FormField.vue'
import PageSection from './PageSection.vue'
import PasswordInput from './PasswordInput.vue'
import SegmentedControl from './SegmentedControl.vue'
import VersionLink from './VersionLink.vue'

// 登录卡: 登录页(LoginView)和组件样例的登录场景共用. 居中的一张卡片(4 列布局中占中间 2 列), 从上到下: 图标块, 标题, 密码, 登录和无密码 IP 访问
// (各占一行的大按钮), 页脚(左边版本, 右边语言). 标题: 登录页(没有页头)用 h1, 样例场景里是 h2.
// password: 是否允许密码登录(默认允许); certificate: 是否显示证书登录按钮(服务器的登录方式设置).
withDefaults(
  defineProps<{
    error?: string
    busy?: boolean
    ipHint?: boolean
    canSubmit?: boolean
    heading?: 'h1' | 'h2'
    password?: boolean
    certificate?: boolean
  }>(),
  { password: true },
)
const emit = defineEmits<{ submit: []; ip: []; certificate: [] }>()
const value = defineModel<string>({ default: '' })
const { t, locale } = useI18n()
const localeOptions = LOCALES.map((value) => ({ value, label: NATIVE_NAMES[value] }))
const currentLocale = computed({
  get: () => locale.value as Locale,
  set: (value: Locale) => (locale.value = value),
})
</script>

<template>
  <CardForm @submit.prevent="emit('submit')">
    <PageSection :cols="2" :col="2" :title="t('page.login')" :heading="heading">
      <template #lead>
        <div>
          <span class="flex size-12 items-center justify-center rounded-md bg-accent text-accent-foreground">
            <Lock class="size-6" aria-hidden="true" />
          </span>
        </div>
      </template>
      <p v-if="!password && error" role="alert" class="text-sm text-destructive">{{ error }}</p>
      <FormField v-if="password" v-slot="field" :label="t('login.password')" :error="error">
        <PasswordInput
          :id="field.id"
          v-model="value"
          size="lg"
          autocomplete="current-password"
          :aria-invalid="field.invalid"
          :aria-describedby="field.describedby"
        />
      </FormField>
      <FormActions block>
        <Button v-if="certificate" :type="password ? 'button' : 'submit'" size="lg" :variant="password ? 'outline' : 'default'" :disabled="busy" @click.prevent="emit('certificate')">
          <span class="truncate">{{ t('login.certificate') }}</span>
        </Button>
        <Button v-if="password" type="submit" size="lg" :disabled="busy || !canSubmit">{{ t('login.submit') }}</Button>
        <Button type="button" size="lg" variant="outline" :disabled="busy" @click="emit('ip')">
          <span class="truncate">{{ t('login.ipAccess') }}</span>
        </Button>
      </FormActions>
      <p v-if="ipHint" role="status" class="text-sm text-muted-foreground">{{ t('login.ipDenied') }}</p>
      <!-- 页脚: 宽时左边版本, 右边语言(窄时各占一行) -->
      <div class="flex items-center" v-bind="blockAttrs({ span: 4 })">
        <VersionLink />
      </div>
      <FormField :label="t('settings.language')" group hide-label :span="8">
        <SegmentedControl v-model="currentLocale" :options="localeOptions" :label="t('settings.language')" />
      </FormField>
    </PageSection>
  </CardForm>
</template>
