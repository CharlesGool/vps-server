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
import { ApiError, api, isSignedOut } from '@/lib/api'
import { errorText, fieldError } from '@/lib/errors'
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
  // 规则被拒绝时, 是哪一项和原因(见 errors.ts)
  field?: string
  reason?: string
}

const { t } = useI18n()
const data = ref<Portfwd>()
const busy = ref(false)
const GOOD = ['portfwd_added', 'portfwd_removed', 'portfwd_enabled', 'portfwd_disabled']

// 服务器指出被拒绝的输入项时, 提示和对应的字段用这些标签
const labels = computed(() => ({
  label: t('console.portfwd_label'),
  protocol: t('console.portfwd_protocol'),
  publicPort: t('console.portfwd_public_port'),
  targetHost: t('console.portfwd_target_host'),
  targetPort: t('console.portfwd_target_port'),
}))
// 最近一次被拒绝的添加(成功后清空), 用来标出对应的字段
const failure = ref<unknown>()
const invalid = (field: string) => fieldError(failure.value, field)
function apply(value: Portfwd) {
  data.value = value
  // 添加被拒绝时服务器仍返回页面状态, 带上消息和被拒绝的输入项
  failure.value = value.field ? new ApiError(200, value.message ?? '', { field: value.field, reason: value.reason }) : undefined
  if (!value.message) return
  const text = value.message === 'portfwd_invalid' && failure.value ? errorText(failure.value, { labels: labels.value }) : t(`console.${value.message}`, { max: value.max })
  showToast(text, GOOD.includes(value.message) ? 'success' : 'destructive')
}
onMounted(async () => {
  try {
    apply(await api<Portfwd>('portfwd'))
  } catch (err) {
    if (!isSignedOut(err)) showToast(errorText(err), 'destructive')
  }
})
async function send(path: string, body: unknown) {
  busy.value = true
  try {
    apply(await api<Portfwd>(path, { method: 'POST', body }))
    return data.value?.message ? GOOD.includes(data.value.message) : false
  } catch (err) {
    if (!isSignedOut(err)) {
      failure.value = err
      showToast(errorText(err, { labels: labels.value }), 'destructive')
    }
    return false
  } finally {
    busy.value = false
  }
}

const PROTOCOLS = { tcp: 'TCP', udp: 'UDP', both: 'TCP+UDP' } as const
const protocolOptions = (Object.keys(PROTOCOLS) as (keyof typeof PROTOCOLS)[]).map((value) => ({ value, label: PROTOCOLS[value] }))
const state = (rule: Rule) =>
  rule.applied
    ? { tone: 'success' as const, text: t('console.portfwd_state_on') }
    : rule.enabled
      ? { tone: 'destructive' as const, text: t('console.portfwd_state_failed') }
      : { tone: 'neutral' as const, text: t('console.portfwd_state_off') }
const facts = computed(() => [
  { key: 'state', label: t('vps.modules.status') },
  { key: 'protocol', label: t('console.portfwd_protocol') },
  { key: 'public', label: t('console.portfwd_public_port') },
  { key: 'host', label: t('console.portfwd_target_host'), mono: true },
  { key: 'target', label: t('console.portfwd_target_port') },
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
    <PageHeader :title="t('console.portfwd_heading')" :description="t('vps.portfwd.description')" />

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <template v-else>
      <PageSection v-if="!data.rules.length" :cols="4" :title="t('vps.portfwd.rules')">
        <EmptyState :icon="Route" :title="t('console.portfwd_none')" />
      </PageSection>

      <PageSection v-for="rule in data.rules" :key="rule.id" :cols="4" :title="rule.label || rule.id">
        <DescriptionList :items="facts">
          <template #value-state>
            <StatusBadge :tone="state(rule).tone">{{ state(rule).text }}</StatusBadge>
          </template>
          <template #value-protocol>{{ PROTOCOLS[rule.protocol] }}</template>
          <template #value-public>
            <PrivateValue :source="`forward-${rule.id}`" field="public-port" :label="t('console.portfwd_public_port')" />
          </template>
          <template #value-host>{{ rule.targetHost }}</template>
          <template #value-target>
            <PrivateValue :source="`forward-${rule.id}`" field="target-port" :label="t('console.portfwd_target_port')" />
          </template>
        </DescriptionList>
        <TrafficCard :feature="`portfwd:${rule.id}`" inline />
        <FormActions>
          <ConfirmDialog
            :title="t('vps.portfwd.deleteTitle', { name: rule.label || rule.id })"
            :description="t('vps.portfwd.deleteDescription')"
            :confirm-label="t('console.portfwd_delete')"
            danger
            @confirm="send('portfwd/delete', { id: rule.id })"
          >
            <template #trigger>
              <Button variant="destructive" :disabled="busy"><Trash2 aria-hidden="true" />{{ t('console.portfwd_delete') }}</Button>
            </template>
          </ConfirmDialog>
          <Button variant="outline" :disabled="busy" @click="send(rule.enabled ? 'portfwd/disable' : 'portfwd/enable', { id: rule.id })">
            <component :is="rule.enabled ? PowerOff : Power" aria-hidden="true" />{{ rule.enabled ? t('console.portfwd_disable') : t('console.portfwd_enable') }}
          </Button>
        </FormActions>
      </PageSection>

      <CardForm v-if="data.canAdd" @submit.prevent="add">
        <PageSection :cols="4" :title="t('console.portfwd_add')" :description="t('console.portfwd_howto')">
          <FormField v-slot="field" :label="t('console.portfwd_label')" :span="4" :error="invalid('label')">
            <Input :id="field.id" v-model="form.label" maxlength="80" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
          </FormField>
          <FormField :label="t('console.portfwd_protocol')" group :span="8" :error="invalid('protocol')">
            <SegmentedControl v-model="form.protocol" :options="protocolOptions" :label="t('console.portfwd_protocol')" />
          </FormField>
          <FormField v-slot="field" :label="t('console.portfwd_public_port')" :span="4" :error="invalid('publicPort')">
            <NumberField :id="field.id" v-model="form.publicPort" :min="0" :max="65535" :grouping="false" />
          </FormField>
          <FormField v-slot="field" :label="t('console.portfwd_target_host')" :span="4" :error="invalid('targetHost')">
            <Input :id="field.id" v-model="form.targetHost" inputmode="decimal" placeholder="100.x.x.x" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
          </FormField>
          <FormField v-slot="field" :label="t('console.portfwd_target_port')" :span="4" :error="invalid('targetPort')">
            <NumberField :id="field.id" v-model="form.targetPort" :min="0" :max="65535" :grouping="false" />
          </FormField>
          <FormActions>
            <Button type="submit" :disabled="busy"><Plus aria-hidden="true" />{{ t('console.portfwd_add') }}</Button>
          </FormActions>
        </PageSection>
      </CardForm>
      <PageSection v-else :cols="4" :title="t('console.portfwd_add')">
        <AlertBanner tone="warning">{{ t('console.portfwd_module_disabled') }}</AlertBanner>
      </PageSection>
    </template>
  </CardGrid>
</template>
