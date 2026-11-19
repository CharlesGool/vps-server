<script setup lang="ts">
import { ShieldCheck } from '@lucide/vue'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CardForm from '@/components/app/CardForm.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageSection from '@/components/app/PageSection.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/api'
import { verifyAdmin } from '@/lib/session'

// vps-server 项目组件: 敏感页面(终端, FRP 编辑等)进入前的管理员密码验证, 居中的窄卡片(和安全设置的验证相同).
// 验证成功后发出 verified; ipOnly 时(IP 免密会话)只说明需要用密码登录, 没有输入框.
defineProps<{ ipOnly?: boolean }>()
const emit = defineEmits<{ verified: [] }>()
const { t } = useI18n()
const password = ref('')
const error = ref('')
const busy = ref(false)
watch(password, () => (error.value = ''))

async function verify() {
  if (busy.value || !password.value) return
  busy.value = true
  try {
    await verifyAdmin(password.value)
    password.value = ''
    emit('verified')
  } catch (err) {
    error.value =
      err instanceof ApiError && err.code === 'too_many_attempts'
        ? t('login.tooManyAttempts', { seconds: Number(err.data.retryAfter ?? 0) })
        : err instanceof ApiError && err.code === 'invalid_password'
          ? t('login.invalidPassword')
          : t('security.failed')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <PageSection v-if="ipOnly" :cols="2" :col="2" :title="t('security.verifyTitle')" :description="t('security.ipSession')" />
  <CardForm v-else @submit.prevent="verify">
    <PageSection :cols="2" :col="2" :title="t('security.verifyTitle')" :description="t('vps.verify.description')">
      <FormField v-slot="field" :label="t('security.adminPassword')" :error="error">
        <PasswordInput :id="field.id" v-model="password" autocomplete="current-password" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormActions>
        <Button type="submit" :disabled="busy || !password"><ShieldCheck aria-hidden="true" />{{ t('security.verify') }}</Button>
      </FormActions>
    </PageSection>
  </CardForm>
</template>
