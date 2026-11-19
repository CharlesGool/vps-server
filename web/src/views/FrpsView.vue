<script setup lang="ts">
import { Pencil } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppDialog from '@/components/app/AppDialog.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import ModuleInstall from '@/components/vps/ModuleInstall.vue'
import PrivateValue from '@/components/vps/PrivateValue.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// FRPS: 本机的 FRP 服务端. 运行开关, 监听地址, 端口和 token 默认遮住, 本机地址(给客户端填写), 编辑端口和 token 的对话框, 流量.
interface Frps {
  installed: boolean
  node: { running: boolean; bind: string; addresses: { index: number; label: string }[] } | null
}
const { t } = useI18n()
const data = ref<Frps>()
const busy = ref(false)

async function load() {
  try {
    data.value = await api<Frps>('frps')
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)
async function send(path: string, body: unknown, method = 'POST') {
  busy.value = true
  try {
    data.value = await api<Frps>(path, { method, body })
    showToast(t('legacy.frp_saved'), 'success')
    return true
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('legacy.frp_save_failed'), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

const facts = computed(() => [
  { key: 'bind', label: t('legacy.frps_bind'), value: data.value?.node?.bind, mono: true },
  { key: 'port', label: t('legacy.proxy_port') },
  { key: 'token', label: t('legacy.frps_token') },
])
const addressItems = computed(() => (data.value?.node?.addresses ?? []).map((item) => ({ key: String(item.index), label: item.label })))

const editOpen = ref(false)
const port = ref('')
const token = ref('')
function openEdit() {
  port.value = ''
  token.value = ''
  editOpen.value = true
}
async function save() {
  const value = port.value.trim()
  if (value && !/^\d+$/.test(value)) return showToast(t('legacy.frp_save_failed'), 'destructive')
  if (await send('frps/save', { port: value ? Number(value) : null, token: token.value }, 'PUT')) editOpen.value = false
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('legacy.frps_heading')" :description="t('vps.frps.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <ModuleInstall v-else-if="!data.installed || !data.node" module="frps" name="FRPS" @installed="load" />

    <template v-else>
      <PageSection :cols="4" title="FRPS" :description="t('legacy.frp_server_edit_note')">
        <SwitchField
          :model-value="data.node.running"
          :label="t('vps.frps.running')"
          :description="t(data.node.running ? 'legacy.node_active' : 'legacy.frp_not_running')"
          :disabled="busy"
          @update:model-value="(value: boolean) => send('frps/toggle', { enable: value })"
        />
        <DescriptionList :items="facts">
          <template #value-port>
            <PrivateValue source="frps" field="port" :label="t('legacy.proxy_port')" />
          </template>
          <template #value-token>
            <PrivateValue source="frps" field="credential" :label="t('legacy.frps_token')" />
          </template>
        </DescriptionList>
        <FormActions>
          <Button variant="outline" :disabled="busy" @click="openEdit"><Pencil aria-hidden="true" />{{ t('legacy.frp_edit_server') }}</Button>
        </FormActions>
      </PageSection>

      <PageSection v-if="addressItems.length" :cols="4" :title="t('legacy.frp_addresses')" :description="t('legacy.frp_address_note')">
        <DescriptionList :items="addressItems">
          <template v-for="item in addressItems" :key="item.key" #[`value-${item.key}`]>
            <PrivateValue :source="`interface-${item.key}`" field="address" :label="item.label" />
          </template>
        </DescriptionList>
      </PageSection>

      <TrafficCard feature="frps" />
    </template>

    <AppDialog v-model:open="editOpen" :title="t('legacy.frp_edit_server')" :description="t('legacy.frp_server_edit_note')">
      <FormField v-slot="field" :label="t('legacy.proxy_port')" :span="6">
        <Input :id="field.id" v-model="port" inputmode="numeric" maxlength="5" :placeholder="t('legacy.frp_port_keep')" autocomplete="off" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.frps_token')" :span="6">
        <PasswordInput :id="field.id" v-model="token" maxlength="128" autocomplete="new-password" :placeholder="t('legacy.frp_token_keep')" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="editOpen = false">{{ t('legacy.node_cancel') }}</Button>
        <Button :disabled="busy" @click="save">{{ t('legacy.frp_save') }}</Button>
      </template>
    </AppDialog>
  </CardGrid>
</template>
