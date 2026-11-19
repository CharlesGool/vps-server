<script setup lang="ts">
import { Pencil, Plus, Route } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import RadioField from '@/components/app/RadioField.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import SwitchField from '@/components/app/SwitchField.vue'
import ModuleInstall from '@/components/vps/ModuleInstall.vue'
import PrivateValue from '@/components/vps/PrivateValue.vue'
import QrCode from '@/components/vps/QrCode.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// Singbox 节点: 每个节点一张整行卡片(启停开关, 端口和凭据默认遮住, SNI, 访问范围, 本机地址, Clash 订阅的复制/导入/二维码, 流量,
// 编辑和访问范围的对话框, 随机重置和删除), 最后是新建节点的表单.
type Node = {
  id: string
  number: number
  name: string
  protocol: string
  enabled: boolean
  active: boolean
  sni: string | null
  route: string
  access: { mode: 'all' | 'internet' | 'custom'; destinations: string[] }
}
interface Proxy {
  installed: boolean
  available?: boolean
  running?: boolean
  protocols?: string[]
  share?: boolean
  addresses?: { index: number; label: string }[]
  nodes?: Node[]
  message?: string | null
}

const { t } = useI18n()
const data = ref<Proxy>()
const busy = ref(false)

function apply(value: Proxy) {
  data.value = value
  if (value.message) showToast(t(`legacy.${value.message}`), 'success')
}
async function load() {
  try {
    apply({ ...(await api<Proxy>('proxy')), message: null })
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)
async function send(path: string, body: unknown, method = 'POST') {
  busy.value = true
  try {
    apply(await api<Proxy>(path, { method, body }))
    return true
  } catch (err) {
    if (!isSignedOut(err)) showToast(t(err instanceof ApiError && err.code === 'invalid_destinations' ? 'vps.proxy.invalidDestinations' : 'legacy.node_settings_failed'), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

const summary = computed(() => {
  const nodes = data.value?.nodes ?? []
  return t('vps.proxy.summary', { total: nodes.length, active: nodes.filter((node) => node.active).length })
})
const status = (node: Node) =>
  !node.enabled ? { tone: 'neutral' as const, key: 'legacy.node_disabled' } : node.active ? { tone: 'success' as const, key: 'legacy.node_active' } : { tone: 'warning' as const, key: 'legacy.node_stopped' }
const facts = (node: Node) => [
  { key: 'port', label: t('legacy.proxy_port') },
  { key: 'credential', label: t('legacy.node_credential') },
  { key: 'sni', label: t('legacy.proxy_sni'), value: node.sni === null ? t('legacy.node_not_applicable') : node.sni || '—' },
  { key: 'route', label: t('legacy.node_route_label'), value: node.route },
  ...(data.value?.addresses ?? []).map((item) => ({ key: `address-${item.index}`, label: item.label })),
  ...(data.value?.share ? [{ key: 'share', label: t('vps.proxy.share') }] : []),
]

// ---- Clash 订阅: 导入和二维码 ----
const shareUrl = async (node: Node) => (await api<{ value: string }>(`private-value?id=${encodeURIComponent(node.id)}&field=share`)).value
async function importClash(node: Node) {
  try {
    window.location.href = `clash://install-config?url=${encodeURIComponent(await shareUrl(node))}`
  } catch {
    showToast(t('legacy.private_value_failed'), 'destructive')
  }
}
const qr = ref<{ name: string; text: string }>()
const qrOpen = computed({
  get: () => qr.value !== undefined,
  set: (open) => {
    if (!open) qr.value = undefined
  },
})
async function showQr(node: Node) {
  try {
    qr.value = { name: node.name, text: `clash://install-config?url=${encodeURIComponent(await shareUrl(node))}` }
  } catch {
    showToast(t('legacy.private_value_failed'), 'destructive')
  }
}

// ---- 编辑 ----
const editing = ref<Node>()
const editOpen = ref(false)
const edit = ref({ name: '', port: '', credential: '', sni: '' })
function openEdit(node: Node) {
  editing.value = node
  edit.value = { name: node.name, port: '', credential: '', sni: node.sni ?? '' }
  editOpen.value = true
}
async function saveEdit() {
  const port = edit.value.port.trim()
  if (port && !/^\d+$/.test(port)) return showToast(t('legacy.node_settings_failed'), 'destructive')
  const body = { id: editing.value!.id, name: edit.value.name.trim(), port: port ? Number(port) : null, credential: edit.value.credential, sni: edit.value.sni }
  if (await send('proxy/edit', body, 'PUT')) editOpen.value = false
}

// ---- 访问范围 ----
const accessOpen = ref(false)
const access = ref({ mode: 'all' as Node['access']['mode'], destinations: '' })
const accessModes = computed(() => [
  { value: 'all' as const, label: t('legacy.node_route_all') },
  { value: 'internet' as const, label: t('legacy.node_route_internet') },
  { value: 'custom' as const, label: t('legacy.node_route_custom') },
])
function openAccess(node: Node) {
  editing.value = node
  access.value = { mode: node.access.mode, destinations: node.access.destinations.join('\n') }
  accessOpen.value = true
}
async function saveAccess() {
  if (await send('proxy/access', { id: editing.value!.id, ...access.value }, 'PUT')) accessOpen.value = false
}

// ---- 新建 ----
const create = ref({ protocol: 'anytls', name: '', port: '', credential: '', sni: 'www.bing.com' })
const protocolOptions = computed(() => (data.value?.protocols ?? []).map((value) => ({ value, label: value })))
async function submitCreate() {
  const port = create.value.port.trim()
  if (port && !/^\d+$/.test(port)) return showToast(t('legacy.node_settings_failed'), 'destructive')
  const ok = await send('proxy/create', { ...create.value, name: create.value.name.trim(), port: port ? Number(port) : null })
  if (ok) create.value = { protocol: create.value.protocol, name: '', port: '', credential: '', sni: 'www.bing.com' }
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('legacy.proxy_heading')" :description="data?.nodes ? summary : t('vps.proxy.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <ModuleInstall v-else-if="!data.installed" module="proxy_nodes" :name="t('legacy.proxy')" @installed="load" />

    <PageSection v-else-if="!data.available" :cols="4" :title="t('legacy.proxy_heading')">
      <AlertBanner tone="destructive">{{ t('legacy.node_state_unavailable') }}</AlertBanner>
    </PageSection>

    <template v-else>
      <PageSection v-if="!data.nodes?.length" :cols="4" :title="t('vps.proxy.nodes')">
        <EmptyState :icon="Route" :title="t('legacy.node_empty')" />
      </PageSection>

      <PageSection v-for="node in data.nodes" :key="node.id" :cols="4" :title="`#${node.number} · ${node.name}`">
        <InlineGroup>
          <StatusBadge tone="info">{{ node.protocol }}</StatusBadge>
          <StatusBadge :tone="status(node).tone">{{ t(status(node).key) }}</StatusBadge>
        </InlineGroup>
        <SwitchField
          :model-value="node.enabled"
          :label="t('vps.proxy.enabledName', { name: node.name })"
          :disabled="busy"
          @update:model-value="(value: boolean) => send('proxy/toggle', { id: node.id, enabled: value })"
        />
        <DescriptionList :items="facts(node)">
          <template #value-port>
            <PrivateValue :source="node.id" field="port" :label="`${t('legacy.proxy_port')} ${node.name}`" />
          </template>
          <template #value-credential>
            <PrivateValue :source="node.id" field="credential" :label="`${t('legacy.node_credential')} ${node.name}`" />
          </template>
          <template v-for="item in data.addresses ?? []" :key="item.index" #[`value-address-${item.index}`]>
            <PrivateValue :source="`interface-${item.index}`" field="address" :label="item.label" />
          </template>
          <template #value-share>
            <PrivateValue :source="node.id" field="share" :label="`${t('vps.proxy.share')} ${node.name}`" :reveal="false" />
          </template>
        </DescriptionList>
        <TrafficCard :feature="`node:${node.id}`" inline />
        <FormActions>
          <ActionMenu
            v-if="data.share"
            :label="t('vps.proxy.share')"
            :items="[
              { key: 'import', label: t('legacy.node_clash_import') },
              { key: 'qr', label: t('legacy.node_clash_qr') },
            ]"
            @select="(key: string) => (key === 'import' ? importClash(node) : showQr(node))"
          />
          <ConfirmDialog :title="t('legacy.node_delete')" :description="t('legacy.node_delete_confirm')" :confirm-label="t('legacy.node_delete')" danger @confirm="send('proxy/delete', { id: node.id, confirm: true })">
            <template #trigger>
              <Button variant="destructive" :disabled="busy" :aria-label="`${t('legacy.node_delete')} ${node.name}`">{{ t('legacy.node_delete') }}</Button>
            </template>
          </ConfirmDialog>
          <ConfirmDialog :title="t('legacy.node_random_reset')" :description="t('legacy.node_random_confirm')" :confirm-label="t('legacy.node_random_reset')" danger @confirm="send('proxy/reset', { id: node.id, confirm: true })">
            <template #trigger>
              <Button variant="destructive" :disabled="busy" :aria-label="`${t('legacy.node_random_reset')} ${node.name}`">{{ t('legacy.node_random_reset') }}</Button>
            </template>
          </ConfirmDialog>
          <Button variant="outline" :disabled="busy" @click="openAccess(node)"><Route aria-hidden="true" />{{ t('legacy.node_route_manage') }}</Button>
          <Button variant="outline" :disabled="busy" @click="openEdit(node)"><Pencil aria-hidden="true" />{{ t('legacy.node_manage') }}</Button>
        </FormActions>
      </PageSection>

      <CardForm v-if="data.protocols?.length" @submit.prevent="submitCreate">
        <PageSection :cols="4" :title="t('legacy.node_create')">
          <FormField :label="t('legacy.node_protocol')" group>
            <SegmentedControl v-model="create.protocol" :options="protocolOptions" :label="t('legacy.node_protocol')" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.node_name')" :span="6">
            <Input :id="field.id" v-model="create.name" maxlength="64" autocomplete="off" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.proxy_port')" :span="6">
            <Input :id="field.id" v-model="create.port" inputmode="numeric" maxlength="5" :placeholder="t('legacy.node_random_port')" autocomplete="off" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.node_credential')" :span="create.protocol === 'shadowsocks' ? 12 : 6">
            <PasswordInput :id="field.id" v-model="create.credential" autocomplete="new-password" :placeholder="t('legacy.node_credential_random')" />
          </FormField>
          <FormField v-if="create.protocol !== 'shadowsocks'" v-slot="field" :label="t('legacy.proxy_sni')" :span="6">
            <Input :id="field.id" v-model="create.sni" maxlength="253" :placeholder="t('legacy.node_sni_optional')" autocomplete="off" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy || !create.name.trim()"><Plus aria-hidden="true" />{{ t('legacy.node_create') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>
    </template>

    <AppDialog v-model:open="editOpen" :title="`${t('legacy.node_manage')} ${editing?.name ?? ''}`">
      <FormField v-slot="field" :label="t('legacy.node_name')" :span="6">
        <Input :id="field.id" v-model="edit.name" maxlength="64" autocomplete="off" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.proxy_port')" :span="6">
        <Input :id="field.id" v-model="edit.port" inputmode="numeric" maxlength="5" :placeholder="t('legacy.node_keep_port')" autocomplete="off" />
      </FormField>
      <FormField v-slot="field" :label="t('legacy.node_credential')" :span="editing?.sni === null ? 12 : 6">
        <PasswordInput :id="field.id" v-model="edit.credential" autocomplete="new-password" :placeholder="t('legacy.node_keep_credential')" />
      </FormField>
      <FormField v-if="editing?.sni !== null" v-slot="field" :label="t('legacy.proxy_sni')" :span="6">
        <Input :id="field.id" v-model="edit.sni" maxlength="253" autocomplete="off" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="editOpen = false">{{ t('legacy.node_cancel') }}</Button>
        <Button :disabled="busy || !edit.name.trim()" @click="saveEdit">{{ t('legacy.node_save_settings') }}</Button>
      </template>
    </AppDialog>

    <AppDialog v-model:open="accessOpen" :title="`${t('legacy.node_route_manage')} ${editing?.name ?? ''}`" :description="t('legacy.node_route_hint')">
      <FormField :label="t('legacy.node_route_label')" group>
        <RadioField v-model="access.mode" :options="accessModes" :label="t('legacy.node_route_label')" />
      </FormField>
      <FormField v-if="access.mode === 'custom'" v-slot="field" :label="t('legacy.node_route_destinations')">
        <Textarea :id="field.id" v-model="access.destinations" maxlength="8000" spellcheck="false" :placeholder="t('vps.proxy.destinationsExample')" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="accessOpen = false">{{ t('legacy.node_cancel') }}</Button>
        <Button :disabled="busy" @click="saveAccess">{{ t('legacy.node_route_save') }}</Button>
      </template>
    </AppDialog>

    <AppDialog v-model:open="qrOpen" :title="`${t('legacy.node_clash_qr')} ${qr?.name ?? ''}`">
      <QrCode v-if="qr" :text="qr.text" :label="`${t('legacy.node_clash_qr')} ${qr.name}`" />
    </AppDialog>

  </CardGrid>
</template>
