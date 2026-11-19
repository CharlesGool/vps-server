<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import CardGrid from '@/components/app/CardGrid.vue'
import LoginPanel from '@/components/app/LoginPanel.vue'
import { ApiError } from '@/lib/api'
import { loginByIp, loginWithCertificate, loginWithPassword, session } from '@/lib/session'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const password = ref('')
const busy = ref(false)
const error = ref('')
const ipHint = ref(false)


function done() {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  router.replace(redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/')
}

// 证书按钮只在允许证书登录且本次连接出示了有效证书时显示, 与旧登录页一致
const methods = computed(() => session.value?.loginMethods ?? { password: true, certificate: false, certificatePresented: false })

const MESSAGES: Record<string, string> = {
  invalid_password: 'login.invalidPassword',
  password_disabled: 'login.passwordDisabled',
  certificate_missing: 'login.certificateMissing',
  certificate_disabled: 'login.certificateDisabled',
}

function message(err: unknown) {
  if (err instanceof ApiError && err.code === 'too_many_attempts') {
    return t('login.tooManyAttempts', { seconds: Number(err.data.retryAfter ?? 0) })
  }
  if (err instanceof ApiError && MESSAGES[err.code]) return t(MESSAGES[err.code]!)
  return t('login.failed')
}

async function certificateLogin() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  ipHint.value = false
  try {
    await loginWithCertificate()
    done()
  } catch (err) {
    error.value = message(err)
  } finally {
    busy.value = false
  }
}

async function submit() {
  if (busy.value || !password.value) return
  busy.value = true
  error.value = ''
  ipHint.value = false
  try {
    await loginWithPassword(password.value)
    done()
  } catch (err) {
    error.value = message(err)
  } finally {
    busy.value = false
  }
}

async function ipAccess() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  ipHint.value = false
  try {
    if (await loginByIp()) done()
    else ipHint.value = true
  } catch (err) {
    error.value = message(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <CardGrid>
    <!-- 登录页: 只有居中的登录卡, 卡片标题(h1)就是页面标题 -->
    <LoginPanel
      v-model="password"
      heading="h1"
      :error="error"
      :busy="busy"
      :ip-hint="ipHint"
      :can-submit="!!password"
      :password="methods.password"
      :certificate="methods.certificate && methods.certificatePresented"
      @submit="submit"
      @ip="ipAccess"
      @certificate="certificateLogin"
    />
  </CardGrid>
</template>
