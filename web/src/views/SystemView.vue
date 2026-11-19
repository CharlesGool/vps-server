<script setup lang="ts">
import { Save } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import { api } from '@/lib/api'
import { useSecurePage } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// 系统: 进入前要验证管理员密码(和终端相同). 两张半行卡片: 左边系统信息(描述列表), 右边修改主机名(表单).
// 系统更新, 进程, 服务和监听端口各有自己的页面; SSH 登录记录在最近访问页.
interface Info { hostname: string; os: string; kernel: string; arch: string }

const { t, te } = useI18n()
const { state, guard } = useSecurePage()
const info = ref<Info>()
const hostname = ref('')
const busy = ref(false)

const errorText = (code: string) => (te(`vps.system.error.${code}`) ? t(`vps.system.error.${code}`) : undefined)

async function load() {
  const value = await guard(() => api<Info>('system'))
  if (!value) return
  info.value = value
  hostname.value = value.hostname
  state.value = 'ready'
}
onMounted(load)

async function saveHostname() {
  busy.value = true
  const value = await guard(() => api<Info>('system/hostname', { method: 'POST', body: { name: hostname.value } }), errorText)
  busy.value = false
  if (value) {
    info.value = value
    showToast(t('vps.system.hostnameSaved'), 'success')
  }
}

const infoItems = computed(() => [
  { key: 'hostname', label: t('vps.system.hostname'), value: info.value?.hostname, mono: true },
  { key: 'os', label: t('vps.system.os'), value: info.value?.os },
  { key: 'kernel', label: t('vps.system.kernel'), value: info.value?.kernel, mono: true },
  { key: 'arch', label: t('vps.system.arch'), value: info.value?.arch, mono: true },
])
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('vps.system.title')" :description="t('vps.system.description')" />

    <PageSection v-if="state === 'loading'" :cols="4">
      <LoadingState />
    </PageSection>
    <AdminVerify v-else-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="load" />

    <template v-else-if="info">
      <PageSection :cols="2" :title="t('vps.system.info')">
        <DescriptionList :items="infoItems" />
      </PageSection>

      <CardForm @submit.prevent="saveHostname">
        <PageSection :cols="2" :title="t('vps.system.rename')" :description="t('vps.system.hostnameHelp')">
          <FormField v-slot="field" :label="t('vps.system.hostnameLabel')">
            <Input :id="field.id" v-model.trim="hostname" autocomplete="off" spellcheck="false" maxlength="253" :aria-describedby="field.describedby" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy || !hostname || hostname === info.hostname"><Save aria-hidden="true" />{{ t('vps.common.save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>
    </template>
  </CardGrid>
</template>
