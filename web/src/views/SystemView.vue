<script setup lang="ts">
import { PackageCheck, RefreshCw, Save } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DataTable from '@/components/app/DataTable.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import PortsCard from '@/components/vps/PortsCard.vue'
import ProcessesCard from '@/components/vps/ProcessesCard.vue'
import ServicesCard from '@/components/vps/ServicesCard.vue'
import { api } from '@/lib/api'
import { useSecurePage } from '@/lib/secure-page'
import { showToast } from '@/lib/toast'

// 系统: 进入前要验证管理员密码(和终端相同). 第一行主机名(表单)和系统信息(描述列表)两张半行卡片;
// 然后系统更新, 进程, 服务, 监听端口和 SSH 登录记录, 各一张整行卡片.
interface Info { hostname: string; os: string; kernel: string; arch: string }
interface Updates {
  supported: boolean
  packages: { package: string; version: string; current: string }[]
  listsAge: number | null
  running: boolean
  log: string
  lastExit: number | null
}
interface Ssh {
  accepted: { time: string; method: string; user: string; ip: string }[]
  failed: { time: string; user: string; ip: string }[]
  failedTotal: number
  topFailed: { ip: string; count: number }[]
}

const { t, te } = useI18n()
const { state, guard } = useSecurePage()
const info = ref<Info>()
const updates = ref<Updates>()
const ssh = ref<Ssh>()
const hostname = ref('')
const busy = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

const errorText = (code: string) => (te(`vps.system.error.${code}`) ? t(`vps.system.error.${code}`) : undefined)

async function load() {
  const value = await guard(() => api<Info>('system'))
  if (!value) return
  info.value = value
  hostname.value = value.hostname
  state.value = 'ready'
  await Promise.all([loadUpdates(), loadSsh()])
}
async function loadUpdates() {
  clearTimeout(timer)
  const value = await guard(() => api<Updates>('system/updates'))
  if (value) updates.value = value
  if (value?.running) timer = setTimeout(loadUpdates, 3000)
}
async function loadSsh() {
  const value = await guard(() => api<Ssh>('system/ssh'))
  if (value) ssh.value = value
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

async function saveHostname() {
  busy.value = true
  const value = await guard(() => api<Info>('system/hostname', { method: 'POST', body: { name: hostname.value } }), errorText)
  busy.value = false
  if (value) {
    info.value = value
    showToast(t('vps.system.hostnameSaved'), 'success')
  }
}

async function checkUpdates() {
  busy.value = true
  const value = await guard(() => api<Updates>('system/updates/check', { method: 'POST', body: {} }), errorText)
  busy.value = false
  if (value) updates.value = value
}
async function upgrade() {
  busy.value = true
  const value = await guard(() => api<Updates>('system/updates/upgrade', { method: 'POST', body: {} }), errorText)
  busy.value = false
  if (value) {
    updates.value = value
    if (value.running) timer = setTimeout(loadUpdates, 3000)
  }
}

const infoItems = computed(() => [
  { key: 'os', label: t('vps.system.os'), value: info.value?.os },
  { key: 'kernel', label: t('vps.system.kernel'), value: info.value?.kernel, mono: true },
  { key: 'arch', label: t('vps.system.arch'), value: info.value?.arch, mono: true },
])

const pkgPage = ref(1)
const pkgColumns = computed(() => [
  { key: 'package', label: t('vps.system.package'), mono: true },
  { key: 'current', label: t('vps.system.current'), mono: true },
  { key: 'version', label: t('vps.system.available'), mono: true },
])
const pkgRows = computed(() => (updates.value?.packages ?? []).slice((pkgPage.value - 1) * 10, pkgPage.value * 10))
const updatesNote = computed(() => {
  const value = updates.value
  if (!value) return ''
  if (!value.supported) return t('vps.system.aptMissing')
  const age = value.listsAge == null ? '-' : value.listsAge < 3600 ? t('vps.system.minutesAgo', { n: Math.max(1, Math.round(value.listsAge / 60)) }) : t('vps.system.hoursAgo', { n: Math.round(value.listsAge / 3600) })
  return t('vps.system.updatesNote', { n: value.packages.length, age })
})

const sshView = ref<'accepted' | 'failed' | 'top'>('accepted')
const sshPage = ref(1)
watch(sshView, () => (sshPage.value = 1))
const sshViews = computed(() => [
  { value: 'accepted' as const, label: t('vps.system.sshAccepted') },
  { value: 'failed' as const, label: t('vps.system.sshFailed') },
  { value: 'top' as const, label: t('vps.system.sshTop') },
])
const sshAll = computed<Record<string, unknown>[]>(() => {
  const value = ssh.value
  if (!value) return []
  if (sshView.value === 'top') return value.topFailed.map((row) => ({ key: row.ip, ip: row.ip, count: row.count }))
  return (sshView.value === 'accepted' ? value.accepted : value.failed).map((row, index) => ({ key: `${index}`, ...row }))
})
const sshRows = computed(() => sshAll.value.slice((sshPage.value - 1) * 10, sshPage.value * 10))
const sshColumns = computed(() =>
  sshView.value === 'top'
    ? [
        { key: 'ip', label: t('vps.system.ip'), mono: true },
        { key: 'count', label: t('vps.system.failures'), align: 'end' as const, mono: true },
      ]
    : [
        { key: 'time', label: t('vps.system.time'), mono: true },
        { key: 'user', label: t('vps.system.user'), mono: true },
        { key: 'ip', label: t('vps.system.ip'), mono: true },
        ...(sshView.value === 'accepted' ? [{ key: 'method', label: t('vps.system.method') }] : []),
      ],
)
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('vps.system.title')" :description="t('vps.system.description')" />

    <PageSection v-if="state === 'loading'" :cols="4">
      <LoadingState />
    </PageSection>
    <AdminVerify v-else-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="load" />

    <template v-else-if="info">
      <CardForm @submit.prevent="saveHostname">
        <PageSection :cols="2" :title="t('vps.system.hostname')" :description="t('vps.system.hostnameHelp')">
          <FormField v-slot="field" :label="t('vps.system.hostnameLabel')">
            <Input :id="field.id" v-model.trim="hostname" autocomplete="off" spellcheck="false" maxlength="253" :aria-describedby="field.describedby" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy || !hostname || hostname === info.hostname"><Save aria-hidden="true" />{{ t('vps.common.save') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>

      <PageSection :cols="2" :title="t('vps.system.info')">
        <DescriptionList :items="infoItems" />
      </PageSection>


      <PageSection :cols="4" :title="t('vps.system.updates')" :description="updatesNote">
        <AlertBanner v-if="updates?.running" tone="info" role="status">{{ t('vps.system.upgrading') }}</AlertBanner>
        <AlertBanner v-else-if="updates?.lastExit != null && updates.lastExit !== 0" tone="destructive">{{ t('vps.system.upgradeFailed') }}</AlertBanner>
        <DataTable v-if="updates?.supported" :columns="pkgColumns" :rows="pkgRows" row-key="package" :caption="t('vps.system.updates')" :empty="t('vps.system.noUpdates')" />
        <PaginationBar v-if="(updates?.packages.length ?? 0) > 10" v-model="pkgPage" :total="updates?.packages.length ?? 0" />
        <LogOutput v-if="updates?.log" :text="updates.log" :label="t('vps.system.upgradeLog')" />
        <FormActions v-if="updates?.supported">
          <Button variant="outline" :disabled="busy || updates.running" @click="checkUpdates"><RefreshCw aria-hidden="true" />{{ t('vps.system.check') }}</Button>
          <ConfirmDialog :title="t('vps.system.upgradeAll')" :description="t('vps.system.upgradeConfirm')" :confirm-label="t('vps.system.upgradeAll')" @confirm="upgrade">
            <template #trigger>
              <Button :disabled="busy || updates.running || !updates.packages.length"><PackageCheck aria-hidden="true" />{{ t('vps.system.upgradeAll') }}</Button>
            </template>
          </ConfirmDialog>
        </FormActions>
      </PageSection>

      <ProcessesCard :guard="guard" />
      <ServicesCard :guard="guard" />
      <PortsCard :guard="guard" />

      <PageSection :cols="4" :title="t('vps.system.ssh')" :description="ssh ? t('vps.system.sshNote', { n: ssh.failedTotal }) : undefined">
        <FormField :label="t('vps.system.sshShow')" group>
          <SegmentedControl v-model="sshView" :options="sshViews" :label="t('vps.system.sshShow')" />
        </FormField>
        <DataTable :columns="sshColumns" :rows="sshRows" row-key="key" :caption="t('vps.system.ssh')" :empty="t('vps.system.sshEmpty')" />
        <PaginationBar v-if="sshAll.length > 10" v-model="sshPage" :total="sshAll.length" />
      </PageSection>
    </template>
  </CardGrid>
</template>
