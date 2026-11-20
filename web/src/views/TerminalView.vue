<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import TerminalScreen from '@/components/vps/TerminalScreen.vue'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { showToast } from '@/lib/toast'

// 终端: root 终端, 一张整行卡片. 和安全设置一样, 进入前要在最近几分钟内验证过管理员密码.
const { t } = useI18n()
const state = ref<'loading' | 'verify' | 'ip' | 'ready'>('loading')
const token = ref('')

async function load() {
  try {
    token.value = (await api<{ token: string }>('terminal')).token
    state.value = 'ready'
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') state.value = 'verify'
    else if (err instanceof ApiError && err.code === 'password_session_required') state.value = 'ip'
    else if (!isSignedOut(err)) showToast(errorText(err), 'destructive')
  }
}
onMounted(load)
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.terminal_title')" :description="t('vps.terminal.description')" />
    <PageSection v-if="state === 'loading'" :cols="4">
      <LoadingState />
    </PageSection>
    <AdminVerify v-else-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="load" />
    <PageSection v-else :cols="4" :title="t('vps.terminal.session')">
      <TerminalScreen :token="token" :label="t('console.terminal_title')" />
    </PageSection>
  </CardGrid>
</template>
