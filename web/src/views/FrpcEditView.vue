<script setup lang="ts">
import { Pencil, Plus, Save } from '@lucide/vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import AppDialog from '@/components/app/AppDialog.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PasswordInput from '@/components/app/PasswordInput.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import PrivateValue from '@/components/vps/PrivateValue.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, isSignedOut } from '@/lib/api'
import { errorText, fieldError } from '@/lib/errors'
import { showToast } from '@/lib/toast'

// FRPC 实例: 没有 name 时是新建表单; 有 name 时是服务器(遮住的地址, 端口, token, 编辑和重命名), 流量, 代理表格, STCP 访问者表格.
// 每次修改作为后台任务进行(保存会重启实例, 可能断开承载这次请求的隧道), 页面轮询任务结果.
type Proxy = { name: string; type: 'tcp' | 'udp' | 'stcp'; localIP: string; localPort: number; remotePort: number | null }
type Visitor = { name: string; serverName: string; bindAddr: string; bindPort: number }
interface Client {
  name: string
  supported: boolean
  proxies?: Proxy[]
  visitors?: Visitor[]
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const name = computed(() => (typeof route.query.name === 'string' ? route.query.name : ''))
const data = ref<Client>()
const saving = ref(false)

async function load() {
  if (!name.value) return
  try {
    data.value = await api<Client>(`frpc/client?name=${encodeURIComponent(name.value)}`)
  } catch (err) {
    if (isSignedOut(err)) return
    showToast(errorText(err), 'destructive')
    await router.replace('/frpc')
  }
}
watch(name, () => {
  data.value = undefined
  void load()
}, { immediate: true })

// ---- 后台任务 ----
let timer: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(timer))
// 服务器指出被拒绝的输入项时, 提示和对应的字段用这些标签(同一时间只有一个表单或对话框在用)
const labels = computed(() => ({
  name: t('console.frp_instance_name'),
  newName: t('console.frp_instance_name'),
  server: t('console.frp_server_ip'),
  port: t('console.proxy_port'),
  token: t('console.frps_token'),
  'proxy.name': t('console.proxy_name'),
  'proxy.type': t('console.proxy_type'),
  'proxy.localIP': t('console.frp_local_ip'),
  'proxy.localPort': t('console.frp_local_port'),
  'proxy.remotePort': t('console.frp_server_port'),
  'proxy.secretKey': t('console.frp_secret_key'),
  'visitor.name': t('console.proxy_name'),
  'visitor.serverName': t('console.frp_visitor_target'),
  'visitor.bindPort': t('console.frp_visitor_bind_port'),
  'visitor.secretKey': t('console.frp_secret_key'),
}))
// 最近一次被拒绝的修改(新的修改开始或打开对话框时清空), 用来标出对应的字段
const failure = ref<unknown>()
const invalid = (field: string) => fieldError(failure.value, field)
async function change(body: Record<string, unknown>) {
  saving.value = true
  failure.value = undefined
  try {
    const { job, name: next } = await api<{ job: string; name: string }>('frpc/change', { method: 'POST', body })
    await poll(job, next)
    return true
  } catch (err) {
    saving.value = false
    if (!isSignedOut(err)) {
      failure.value = err
      showToast(errorText(err, { codes: () => t('console.frp_save_failed'), labels: labels.value }), 'destructive')
    }
    return false
  }
}
function poll(job: string, next: string) {
  return new Promise<void>((resolve) => {
    const check = async () => {
      let state = 'running'
      try {
        state = (await api<{ state: string }>(`frpc/job?job=${job}`)).state
      } catch {
        // 实例重启时这个请求可能经过刚断开的隧道: 稍后再试
      }
      if (state === 'queued' || state === 'running') {
        timer = setTimeout(check, 1500)
        return
      }
      saving.value = false
      showToast(t(state === 'done' ? 'console.frp_saved' : 'console.frp_save_failed'), state === 'done' ? 'success' : 'destructive')
      if (state === 'done' && next !== name.value) await router.replace({ path: '/frpc/edit', query: { name: next } })
      else if (state === 'done') await load()
      resolve()
    }
    timer = setTimeout(check, 1500)
  })
}

// ---- 新建 ----
const create = ref({ name: '', server: '', port: 7000, token: '' })
async function submitCreate() {
  const value = create.value
  await change({ section: 'create', name: value.name.trim(), server: value.server.trim(), port: value.port, token: value.token })
}

// ---- 服务器 ----
const serverFacts = computed(() => [
  { key: 'server', label: t('console.frp_server_ip') },
  { key: 'port', label: t('console.proxy_port') },
  { key: 'token', label: t('console.frps_token') },
])
const serverOpen = ref(false)
const server = ref({ server: '', port: 7000, token: '' })
async function openServer() {
  server.value = { server: '', port: 7000, token: '' }
  failure.value = undefined
  serverOpen.value = true
  // 填入当前值(页面上遮住, 这里取一次)
  const read = (field: string) => api<{ value: string }>(`private-value?id=${encodeURIComponent(`frpc:${name.value}`)}&field=${field}`).then((reply) => reply.value)
  try {
    const [address, port, token] = await Promise.all([read('server'), read('port'), read('token')])
    server.value = { server: address, port: Number(port), token }
  } catch {
    // 留空让用户填写
  }
}
async function saveServer() {
  if (await change({ section: 'server', name: name.value, ...server.value, server: server.value.server.trim() })) serverOpen.value = false
}
const renameOpen = ref(false)
const newName = ref('')
async function rename() {
  if (await change({ section: 'rename', name: name.value, newName: newName.value.trim() })) renameOpen.value = false
}

// ---- 代理 ----
const proxyColumns = computed(() => [
  { key: 'name', label: t('console.proxy_name') },
  { key: 'type', label: t('console.proxy_type') },
  { key: 'local', label: t('vps.frpc.local'), mono: true },
  { key: 'remote', label: t('console.frp_server_port'), mono: true },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
const types = [
  { value: 'tcp' as const, label: 'TCP' },
  { value: 'udp' as const, label: 'UDP' },
  { value: 'stcp' as const, label: 'STCP' },
]
const proxyOpen = ref(false)
const proxyIndex = ref<number | null>(null)
const proxy = ref({ name: '', type: 'tcp' as Proxy['type'], localIP: '127.0.0.1', localPort: 80, remotePort: 0, secretKey: '' })
function openProxy(index: number | null) {
  const item = index === null ? undefined : data.value?.proxies?.[index]
  proxyIndex.value = index
  proxy.value = item
    ? { name: item.name, type: item.type, localIP: item.localIP, localPort: item.localPort, remotePort: item.remotePort ?? 0, secretKey: '' }
    : { name: '', type: 'tcp', localIP: '127.0.0.1', localPort: 80, remotePort: 0, secretKey: '' }
  failure.value = undefined
  proxyOpen.value = true
}
async function saveProxy() {
  const body = { name: name.value, section: proxyIndex.value === null ? 'add' : 'edit', ...(proxyIndex.value === null ? {} : { index: proxyIndex.value }), proxy: proxy.value }
  if (await change(body)) proxyOpen.value = false
}
const proxyActions = computed(() => [
  { key: 'edit', label: t('console.frp_edit_proxy') },
  { key: 'delete', label: t('console.frp_delete_proxy'), danger: true },
])

// ---- 访问者 ----
const visitorColumns = computed(() => [
  { key: 'name', label: t('console.proxy_name') },
  { key: 'serverName', label: t('console.frp_visitor_target') },
  { key: 'listen', label: t('console.frp_visitor_listen'), mono: true },
  { key: 'secret', label: t('console.frp_secret_key') },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
const visitorOpen = ref(false)
const visitorIndex = ref<number | null>(null)
const visitor = ref({ name: '', serverName: '', bindPort: 6000, secretKey: '' })
function openVisitor(index: number | null) {
  const item = index === null ? undefined : data.value?.visitors?.[index]
  visitorIndex.value = index
  visitor.value = item ? { name: item.name, serverName: item.serverName, bindPort: item.bindPort, secretKey: '' } : { name: '', serverName: '', bindPort: 6000, secretKey: '' }
  failure.value = undefined
  visitorOpen.value = true
}
async function saveVisitor() {
  const body = { name: name.value, section: visitorIndex.value === null ? 'visitor-add' : 'visitor-edit', ...(visitorIndex.value === null ? {} : { index: visitorIndex.value }), visitor: visitor.value }
  if (await change(body)) visitorOpen.value = false
}

// 删除代理或访问者: 确认后进行
const deleting = ref<{ section: 'delete' | 'visitor-delete'; index: number }>()
const deleteOpen = ref(false)
function rowAction(key: string, section: 'proxy' | 'visitor', index: number) {
  if (key === 'edit') {
    if (section === 'proxy') openProxy(index)
    else openVisitor(index)
    return
  }
  deleting.value = { section: section === 'proxy' ? 'delete' : 'visitor-delete', index }
  deleteOpen.value = true
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="name || t('console.frp_new_client')" :trail="[{ to: '/frpc', label: t('console.frp_client_heading') }]" />

    <!-- 新建实例 -->
    <CardForm v-if="!name" @submit.prevent="submitCreate">
      <PageSection :cols="4" :title="t('console.frp_server_settings')">
        <FormField v-slot="field" :label="t('console.frp_instance_name')" :span="6" :error="invalid('name')">
          <Input :id="field.id" v-model="create.name" maxlength="32" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
        </FormField>
        <FormField v-slot="field" :label="t('console.frp_server_ip')" :span="6" :error="invalid('server')">
          <Input :id="field.id" v-model="create.server" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
        </FormField>
        <FormField v-slot="field" :label="t('console.proxy_port')" :span="6" :error="invalid('port')">
          <NumberField :id="field.id" v-model="create.port" :min="1" :max="65535" :grouping="false" />
        </FormField>
        <FormField v-slot="field" :label="t('console.frps_token')" :span="6" :error="invalid('token')">
          <PasswordInput :id="field.id" v-model="create.token" maxlength="128" autocomplete="new-password" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
        </FormField>
        <AlertBanner v-if="saving" tone="info">{{ t('console.frp_saving') }}</AlertBanner>
        <FormActions>
          <Button type="submit" :disabled="saving || !create.name.trim() || !create.server.trim() || !create.token"><Plus aria-hidden="true" />{{ t('console.frp_new_client') }}</Button>
        </FormActions>
      </PageSection>
    </CardForm>

    <PageSection v-else-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <template v-else>
      <PageSection :cols="4" :title="t('console.frp_server_settings')">
        <AlertBanner v-if="saving" tone="info">{{ t('console.frp_saving') }}</AlertBanner>
        <AlertBanner v-if="!data.supported" tone="warning">{{ t('console.frp_unsupported_config') }}</AlertBanner>
        <DescriptionList v-else :items="serverFacts">
          <template v-for="item in serverFacts" :key="item.key" #[`value-${item.key}`]>
            <PrivateValue :source="`frpc:${name}`" :field="item.key" :label="item.label" />
          </template>
        </DescriptionList>
        <FormActions>
          <Button variant="outline" :disabled="saving" @click="((newName = name), (failure = undefined), (renameOpen = true))">{{ t('console.frp_rename_client') }}</Button>
          <Button v-if="data.supported" variant="outline" :disabled="saving" @click="openServer"><Pencil aria-hidden="true" />{{ t('console.frp_edit_target') }}</Button>
        </FormActions>
      </PageSection>

      <TrafficCard :feature="`frpc:${name}`" />

      <template v-if="data.supported">
        <PageSection :cols="4" :title="t('console.frp_proxy_list_heading')">
          <DataTable :columns="proxyColumns" :rows="data.proxies ?? []" row-key="name" :caption="t('console.frp_proxy_list_heading')" :empty="t('console.frp_no_proxies')">
            <template #cell-type="{ row }">{{ row.type.toUpperCase() }}</template>
            <template #cell-local="{ row }">{{ row.localIP }}:{{ row.localPort }}</template>
            <template #cell-remote="{ row, value }">
              <PrivateValue v-if="row.type === 'stcp'" :source="`frpc:${name}`" :field="`proxy-secret:${data.proxies!.indexOf(row)}`" :label="`${t('console.frp_secret_key')} ${row.name}`" />
              <template v-else>{{ value ?? row.remotePort }}</template>
            </template>
            <template #cell-action="{ row }">
              <ActionMenu icon-only :label="`${t('component.moreActions')} ${row.name}`" :items="proxyActions" @select="(key: string) => rowAction(key, 'proxy', data!.proxies!.indexOf(row))" />
            </template>
          </DataTable>
          <FormActions>
            <Button :disabled="saving" @click="openProxy(null)"><Plus aria-hidden="true" />{{ t('console.frp_add_proxy') }}</Button>
          </FormActions>
        </PageSection>

        <PageSection :cols="4" :title="t('console.frp_visitor_heading')" :description="t('console.frp_visitor_note')">
          <DataTable :columns="visitorColumns" :rows="data.visitors ?? []" row-key="name" :caption="t('console.frp_visitor_heading')" :empty="t('vps.frpc.noVisitors')">
            <template #cell-listen="{ row }">{{ row.bindAddr }}:{{ row.bindPort }}</template>
            <template #cell-secret="{ row }">
              <PrivateValue :source="`frpc:${name}`" :field="`visitor-secret:${data.visitors!.indexOf(row)}`" :label="`${t('console.frp_secret_key')} ${row.name}`" />
            </template>
            <template #cell-action="{ row }">
              <ActionMenu icon-only :label="`${t('component.moreActions')} ${row.name}`" :items="proxyActions" @select="(key: string) => rowAction(key, 'visitor', data!.visitors!.indexOf(row))" />
            </template>
          </DataTable>
          <FormActions>
            <Button variant="outline" :disabled="saving" @click="openVisitor(null)"><Plus aria-hidden="true" />{{ t('console.frp_add_visitor') }}</Button>
          </FormActions>
        </PageSection>
      </template>
    </template>

    <AppDialog v-model:open="serverOpen" :title="t('console.frp_edit_target')">
      <FormField v-slot="field" :label="t('console.frp_server_ip')" :error="invalid('server')">
        <Input :id="field.id" v-model="server.server" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormField v-slot="field" :label="t('console.proxy_port')" :span="6" :error="invalid('port')">
        <NumberField :id="field.id" v-model="server.port" :min="1" :max="65535" :grouping="false" />
      </FormField>
      <FormField v-slot="field" :label="t('console.frps_token')" :span="6" :error="invalid('token')">
        <PasswordInput :id="field.id" v-model="server.token" maxlength="128" autocomplete="new-password" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="serverOpen = false">{{ t('console.node_cancel') }}</Button>
        <Button :disabled="saving || !server.server.trim() || !server.token" @click="saveServer"><Save aria-hidden="true" />{{ t('console.frp_save') }}</Button>
      </template>
    </AppDialog>

    <AppDialog v-model:open="renameOpen" :title="t('console.frp_rename_client')">
      <FormField v-slot="field" :label="t('console.frp_instance_name')" :error="invalid('newName')">
        <Input :id="field.id" v-model="newName" maxlength="32" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="renameOpen = false">{{ t('console.node_cancel') }}</Button>
        <Button :disabled="saving || !newName.trim() || newName.trim() === name" @click="rename">{{ t('console.frp_save') }}</Button>
      </template>
    </AppDialog>

    <AppDialog v-model:open="proxyOpen" :title="proxyIndex === null ? t('console.frp_add_proxy') : t('console.frp_edit_proxy')">
      <FormField v-slot="field" :label="t('console.proxy_name')" :span="6" :error="invalid('proxy.name')">
        <Input :id="field.id" v-model="proxy.name" maxlength="64" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormField :label="t('console.proxy_type')" group :span="6" :error="invalid('proxy.type')">
        <SegmentedControl v-model="proxy.type" :options="types" :label="t('console.proxy_type')" />
      </FormField>
      <FormField v-slot="field" :label="t('console.frp_local_ip')" :span="6" :error="invalid('proxy.localIP')">
        <Input :id="field.id" v-model="proxy.localIP" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormField v-slot="field" :label="t('console.frp_local_port')" :span="6" :error="invalid('proxy.localPort')">
        <NumberField :id="field.id" v-model="proxy.localPort" :min="1" :max="65535" :grouping="false" />
      </FormField>
      <FormField v-if="proxy.type === 'stcp'" v-slot="field" :label="t('console.frp_secret_key')" :help="t('console.frp_secret_keep')" :error="invalid('proxy.secretKey')">
        <PasswordInput :id="field.id" v-model="proxy.secretKey" maxlength="128" autocomplete="new-password" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormField v-else v-slot="field" :label="t('console.frp_server_port')" :error="invalid('proxy.remotePort')">
        <NumberField :id="field.id" v-model="proxy.remotePort" :min="0" :max="65535" :grouping="false" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="proxyOpen = false">{{ t('console.node_cancel') }}</Button>
        <Button :disabled="saving || !proxy.name.trim()" @click="saveProxy">{{ t('console.frp_save') }}</Button>
      </template>
    </AppDialog>

    <AppDialog v-model:open="visitorOpen" :title="visitorIndex === null ? t('console.frp_add_visitor') : t('console.frp_edit_proxy')" :description="t('console.frp_visitor_note')">
      <FormField v-slot="field" :label="t('console.proxy_name')" :span="6" :error="invalid('visitor.name')">
        <Input :id="field.id" v-model="visitor.name" maxlength="64" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormField v-slot="field" :label="t('console.frp_visitor_target')" :span="6" :error="invalid('visitor.serverName')">
        <Input :id="field.id" v-model="visitor.serverName" maxlength="64" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormField v-slot="field" :label="t('console.frp_visitor_bind_port')" :span="6" :error="invalid('visitor.bindPort')">
        <NumberField :id="field.id" v-model="visitor.bindPort" :min="1" :max="65535" :grouping="false" />
      </FormField>
      <FormField v-slot="field" :label="t('console.frp_secret_key')" :span="6" :help="visitorIndex === null ? undefined : t('console.frp_secret_keep')" :error="invalid('visitor.secretKey')">
        <PasswordInput :id="field.id" v-model="visitor.secretKey" maxlength="128" autocomplete="new-password" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <template #footer>
        <Button variant="outline" @click="visitorOpen = false">{{ t('console.node_cancel') }}</Button>
        <Button :disabled="saving || !visitor.name.trim() || (visitorIndex === null && !visitor.secretKey)" @click="saveVisitor">{{ t('console.frp_save') }}</Button>
      </template>
    </AppDialog>

    <ConfirmDialog
      v-model:open="deleteOpen"
      :title="t('console.frp_delete_proxy')"
      :description="t('console.frp_delete_confirm')"
      :confirm-label="t('console.frp_delete_proxy')"
      danger
      @confirm="deleting && change({ name, section: deleting.section, index: deleting.index })"
    />
  </CardGrid>
</template>
