<script setup lang="ts">
import { Plus } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import InlineGroup from '@/components/app/InlineGroup.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import ModuleInstall from '@/components/vps/ModuleInstall.vue'
import { Button } from '@/components/ui/button'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// FRPC: 本机的 FRP 客户端实例表格(运行, 连接, 转发数量; 行操作在菜单里: 测试连接, 编辑, 启停, 删除), 新建实例.
// 每个实例的服务器, 代理, 访问者和流量在它的编辑页里.
type Client = { name: string; running: boolean; connected: boolean; count: number; proxies: unknown[]; visitors: unknown[] }
interface Frpc {
  installed: boolean
  binaryMissing: boolean
  clients: Client[]
}
const { t } = useI18n()
const router = useRouter()
const data = ref<Frpc>()
const busy = ref(false)
// 测试连接的结果, 按实例名; 没有测试过时显示服务器报告的连接状态
const tested = ref<Record<string, boolean | 'testing'>>({})

async function load() {
  try {
    data.value = await api<Frpc>('frpc')
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
}
onMounted(load)
async function send(path: string, body: unknown) {
  busy.value = true
  try {
    data.value = await api<Frpc>(path, { method: 'POST', body })
    showToast(t('console.frp_saved'), 'success')
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('console.frp_save_failed'), 'destructive')
  } finally {
    busy.value = false
  }
}
async function test(name: string) {
  tested.value[name] = 'testing'
  try {
    tested.value[name] = (await api<{ connected: boolean }>('frpc/test', { method: 'POST', body: { name } })).connected
  } catch (err) {
    delete tested.value[name]
    if (!isSignedOut(err)) showToast(t(err instanceof ApiError && err.code === 'frp_busy' ? 'console.frp_testing' : 'console.frp_test_failed'), 'destructive')
  }
}

const columns = computed(() => [
  { key: 'name', label: t('console.frp_instance_name') },
  { key: 'state', label: t('vps.modules.status') },
  { key: 'count', label: t('console.frp_proxy_list_heading'), align: 'end' as const, mono: true },
  { key: 'action', label: t('vps.files.actions'), align: 'end' as const },
])
const actions = (client: Client) => [
  { key: 'test', label: t('console.frp_test_connection') },
  { key: 'edit', label: t('console.frp_edit_client_button') },
  { key: 'toggle', label: client.running ? t('console.frp_stop_client') : t('console.frp_start_client') },
  { key: 'delete', label: t('console.frp_delete_client'), danger: true },
]
const deleting = ref<string>()
const deleteOpen = ref(false)
function action(key: string, client: Client) {
  if (key === 'test') void test(client.name)
  else if (key === 'edit') void router.push({ path: '/frpc/edit', query: { name: client.name } })
  else if (key === 'toggle') void send('frpc/toggle', { name: client.name, enable: !client.running })
  else {
    deleting.value = client.name
    deleteOpen.value = true
  }
}
const connection = (client: Client) => {
  const value = tested.value[client.name]
  if (value === 'testing') return { tone: 'info' as const, text: t('console.frp_testing') }
  const connected = value ?? client.connected
  return connected ? { tone: 'success' as const, text: t('console.frp_connected') } : { tone: 'warning' as const, text: t('console.frp_disconnected') }
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.frp_client_heading')" :description="t('vps.frpc.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <ModuleInstall v-else-if="!data.installed" module="frpc" name="FRPC" @installed="load" />

    <PageSection v-else :cols="4" :title="t('console.frp_instances')" :description="t('console.frp_client_note')">
      <AlertBanner v-if="data.binaryMissing" tone="warning">{{ t('console.frp_client_binary_missing') }}</AlertBanner>
      <DataTable :columns="columns" :rows="data.clients" row-key="name" :caption="t('console.frp_instances')" :empty="t('console.frp_no_clients')">
        <template #cell-name="{ row }">
          <RouterLink :to="{ path: '/frpc/edit', query: { name: row.name } }" class="font-medium text-primary underline">{{ row.name }}</RouterLink>
        </template>
        <template #cell-state="{ row }">
          <InlineGroup>
            <StatusBadge :tone="row.running ? 'success' : 'neutral'">{{ t(row.running ? 'console.node_active' : 'console.frp_not_running') }}</StatusBadge>
            <StatusBadge :tone="connection(row).tone" aria-live="polite">{{ connection(row).text }}</StatusBadge>
          </InlineGroup>
        </template>
        <template #cell-count="{ row }">{{ row.proxies.length + row.visitors.length || row.count }}</template>
        <template #cell-action="{ row }">
          <ActionMenu icon-only :label="`${t('component.moreActions')} ${row.name}`" :items="actions(row)" @select="(key: string) => action(key, row)" />
        </template>
      </DataTable>
      <FormActions v-if="!data.binaryMissing">
        <Button as-child>
          <RouterLink to="/frpc/edit"><Plus aria-hidden="true" />{{ t('console.frp_new_client') }}</RouterLink>
        </Button>
      </FormActions>
    </PageSection>

    <ConfirmDialog
      v-model:open="deleteOpen"
      :title="t('console.frp_delete_client')"
      :description="t('console.frp_delete_client_confirm', { name: deleting ?? '' })"
      :confirm-label="t('console.frp_delete_client')"
      danger
      @confirm="deleting && send('frpc/delete', { name: deleting })"
    />
  </CardGrid>
</template>
