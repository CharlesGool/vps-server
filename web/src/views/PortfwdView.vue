<script setup lang="ts">
import { Plus, Power, PowerOff, Route, Trash2 } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import NumberField from '@/components/app/NumberField.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import PrivateValue from '@/components/vps/PrivateValue.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// 端口转发: 每条规则一张整行卡片(状态, 协议, 端口默认遮住, 启停和删除, 这条规则的流量), 最后是添加规则的表单.
interface Rule {
  id: string
  label: string
  protocol: 'tcp' | 'udp' | 'both'
  targetHost: string
  enabled: boolean
  applied: boolean
}
interface Portfwd {
  canAdd: boolean
  max: number
  rules: Rule[]
  message: string | null
}

const { t } = useI18n()
const data = ref<Portfwd>()
const busy = ref(false)
const GOOD = ['portfwd_added', 'portfwd_removed', 'portfwd_enabled', 'portfwd_disabled']

function apply(value: Portfwd) {
  data.value = value
  if (value.message) showToast(t(`legacy.${value.message}`, { max: value.max }), GOOD.includes(value.message) ? 'success' : 'destructive')
}
onMounted(async () => {
  try {
    apply(await api<Portfwd>('portfwd'))
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
  }
})
async function send(path: string, body: unknown) {
  busy.value = true
  try {
    apply(await api<Portfwd>(path, { method: 'POST', body }))
    return data.value?.message ? GOOD.includes(data.value.message) : false
  } catch (err) {
    if (!isSignedOut(err)) showToast(t('vps.common.failed'), 'destructive')
    return false
  } finally {
    busy.value = false
  }
}

const PROTOCOLS = { tcp: 'TCP', udp: 'UDP', both: 'TCP+UDP' } as const
const protocolOptions = (Object.keys(PROTOCOLS) as (keyof typeof PROTOCOLS)[]).map((value) => ({ value, label: PROTOCOLS[value] }))
const state = (rule: Rule) =>
  rule.applied
    ? { tone: 'success' as const, text: t('legacy.portfwd_state_on') }
    : rule.enabled
      ? { tone: 'destructive' as const, text: t('legacy.portfwd_state_failed') }
      : { tone: 'neutral' as const, text: t('legacy.portfwd_state_off') }
const facts = computed(() => [
  { key: 'state', label: t('vps.modules.status') },
  { key: 'protocol', label: t('legacy.portfwd_protocol') },
  { key: 'public', label: t('legacy.portfwd_public_port') },
  { key: 'host', label: t('legacy.portfwd_target_host'), mono: true },
  { key: 'target', label: t('legacy.portfwd_target_port') },
])

// ---- 添加规则 ----
const blank = () => ({ label: '', protocol: 'tcp' as Rule['protocol'], publicPort: 0, targetHost: '', targetPort: 0 })
const form = ref(blank())
async function add() {
  if (await send('portfwd/add', form.value)) form.value = blank()
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('legacy.portfwd_heading')" :description="t('vps.portfwd.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <template v-else>
      <PageSection v-if="!data.rules.length" :cols="4" :title="t('vps.portfwd.rules')">
        <EmptyState :icon="Route" :title="t('legacy.portfwd_none')" />
      </PageSection>

      <PageSection v-for="rule in data.rules" :key="rule.id" :cols="4" :title="rule.label || rule.id">
        <DescriptionList :items="facts">
          <template #value-state>
            <StatusBadge :tone="state(rule).tone">{{ state(rule).text }}</StatusBadge>
          </template>
          <template #value-protocol>{{ PROTOCOLS[rule.protocol] }}</template>
          <template #value-public>
            <PrivateValue :source="`forward-${rule.id}`" field="public-port" :label="t('legacy.portfwd_public_port')" />
          </template>
          <template #value-host>{{ rule.targetHost }}</template>
          <template #value-target>
            <PrivateValue :source="`forward-${rule.id}`" field="target-port" :label="t('legacy.portfwd_target_port')" />
          </template>
        </DescriptionList>
        <TrafficCard :feature="`portfwd:${rule.id}`" inline />
        <FormActions>
          <ConfirmDialog
            :title="t('vps.portfwd.deleteTitle', { name: rule.label || rule.id })"
            :description="t('vps.portfwd.deleteDescription')"
            :confirm-label="t('legacy.portfwd_delete')"
            danger
            @confirm="send('portfwd/delete', { id: rule.id })"
          >
            <template #trigger>
              <Button variant="destructive" :disabled="busy"><Trash2 aria-hidden="true" />{{ t('legacy.portfwd_delete') }}</Button>
            </template>
          </ConfirmDialog>
          <Button variant="outline" :disabled="busy" @click="send(rule.enabled ? 'portfwd/disable' : 'portfwd/enable', { id: rule.id })">
            <component :is="rule.enabled ? PowerOff : Power" aria-hidden="true" />{{ rule.enabled ? t('legacy.portfwd_disable') : t('legacy.portfwd_enable') }}
          </Button>
        </FormActions>
      </PageSection>

      <CardForm v-if="data.canAdd" @submit.prevent="add">
        <PageSection :cols="4" :title="t('legacy.portfwd_add')" :description="t('legacy.portfwd_howto')">
          <FormField v-slot="field" :label="t('legacy.portfwd_label')" :span="4">
            <Input :id="field.id" v-model="form.label" maxlength="80" autocomplete="off" />
          </FormField>
          <FormField :label="t('legacy.portfwd_protocol')" group :span="8">
            <SegmentedControl v-model="form.protocol" :options="protocolOptions" :label="t('legacy.portfwd_protocol')" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.portfwd_public_port')" :span="4">
            <NumberField :id="field.id" v-model="form.publicPort" :min="0" :max="65535" :grouping="false" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.portfwd_target_host')" :span="4">
            <Input :id="field.id" v-model="form.targetHost" inputmode="decimal" placeholder="100.x.x.x" autocomplete="off" />
          </FormField>
          <FormField v-slot="field" :label="t('legacy.portfwd_target_port')" :span="4">
            <NumberField :id="field.id" v-model="form.targetPort" :min="0" :max="65535" :grouping="false" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy"><Plus aria-hidden="true" />{{ t('legacy.portfwd_add') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>
      <PageSection v-else :cols="4" :title="t('legacy.portfwd_add')">
        <AlertBanner tone="warning">{{ t('legacy.portfwd_module_disabled') }}</AlertBanner>
      </PageSection>
    </template>
  </CardGrid>
</template>
