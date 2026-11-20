<script setup lang="ts">
import { Eraser, RefreshCw } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import CardGrid from '@/components/app/CardGrid.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import RadioField from '@/components/app/RadioField.vue'
import SelectMenu from '@/components/app/SelectMenu.vue'
import { Button } from '@/components/ui/button'
import { api, isSignedOut } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { showToast } from '@/lib/toast'

// 详细日志: 上方一张筛选卡片(来源, 等级, 刷新, 清空), 下面每个来源一张整行卡片. 来源和等级写在地址里, 可以直接分享或刷新.
const SOURCES = ['all', 'modules', 'web', 'proxy', 'frps', 'frpc', 'tailscale', 'caddy'] as const
const LEVELS = ['all', 'err', 'warning', 'info', 'debug'] as const
type Source = (typeof SOURCES)[number]
type Level = (typeof LEVELS)[number]
interface Logs {
  source: Source
  level: Level
  // text 为 null: 读不到这个服务的日志
  sections: { source: Exclude<Source, 'all'>; text: string | null }[]
}

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const LABELS: Record<Source, string> = {
  all: 'console.logs_source_all',
  modules: 'console.logs_source_modules',
  web: 'vps.logs.web',
  proxy: 'console.logs_source_proxy',
  frps: 'FRPS',
  frpc: 'FRPC',
  tailscale: 'Tailscale',
  caddy: 'console.domains',
}
const label = (source: Source) => (LABELS[source].includes('.') ? t(LABELS[source]) : LABELS[source])
const LEVEL_LABELS: Record<Level, string> = {
  all: 'console.logs_level_all',
  err: 'console.logs_level_error',
  warning: 'console.logs_level_warning',
  info: 'console.logs_level_info',
  debug: 'console.logs_level_debug',
}
const sourceOptions = computed(() => SOURCES.map((value) => ({ value, label: label(value) })))
const levelOptions = computed(() => LEVELS.map((value) => ({ value, label: t(LEVEL_LABELS[value]) })))

const pick = <T extends string>(value: unknown, allowed: readonly T[]) => (allowed.includes(value as T) ? (value as T) : allowed[0]!)
const source = computed<Source>({
  get: () => pick(route.query.source, SOURCES),
  set: (value) => router.replace({ query: { ...route.query, source: value } }),
})
const level = computed<Level>({
  get: () => pick(route.query.level, LEVELS),
  set: (value) => router.replace({ query: { ...route.query, level: value } }),
})
// 模块操作历史不是系统日志, 没有等级
const filterable = computed(() => source.value !== 'modules')

const data = ref<Logs>()
const loading = ref(false)
async function load() {
  loading.value = true
  try {
    const query = new URLSearchParams({ source: source.value, level: filterable.value ? level.value : 'all' })
    data.value = await api<Logs>(`logs?${query}`)
  } catch (err) {
    if (!isSignedOut(err)) showToast(errorText(err), 'destructive')
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([source, level], load)

const clearing = ref(false)
async function clear() {
  clearing.value = true
  try {
    await api('logs/clear', { method: 'POST', body: { source: source.value } })
    showToast(t('console.logs_clear_done'), 'success')
    await load()
  } catch (err) {
    if (!isSignedOut(err)) showToast(errorText(err), 'destructive')
  } finally {
    clearing.value = false
  }
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.logs')" :description="t('vps.logs.description')" :trail="[{ to: '/settings', label: t('page.settings') }]" />

    <PageSection :cols="4" :title="t('vps.logs.filter')">
      <FormField v-slot="field" :label="t('vps.logs.source')" :span="6">
        <SelectMenu :id="field.id" v-model="source" :options="sourceOptions" :label="t('vps.logs.source')" />
      </FormField>
      <FormField v-if="filterable" :label="t('console.logs_level')" group :span="6">
        <RadioField v-model="level" :options="levelOptions" :label="t('console.logs_level')" />
      </FormField>
      <FormActions>
        <ConfirmDialog :title="t('vps.logs.clearTitle')" :description="t('console.logs_clear_confirm')" :confirm-label="t('console.logs_clear')" danger @confirm="clear">
          <template #trigger>
            <Button variant="outline" :disabled="clearing"><Eraser aria-hidden="true" />{{ t('console.logs_clear') }}</Button>
          </template>
        </ConfirmDialog>
        <Button variant="outline" :disabled="loading" @click="load"><RefreshCw aria-hidden="true" />{{ t('vps.logs.refresh') }}</Button>
      </FormActions>
    </PageSection>

    <PageSection v-if="!data" :cols="4">
      <LoadingState />
    </PageSection>

    <PageSection v-for="section in data?.sections ?? []" :key="section.source" :cols="4" :title="label(section.source)">
      <LogOutput
        :text="section.text === null ? t('console.logs_unavailable') : section.text"
        :label="label(section.source)"
        :empty="t('console.logs_empty')"
      />
    </PageSection>
  </CardGrid>
</template>
