<script setup lang="ts">
import { CircleArrowUp, RefreshCw, RotateCw } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import DescriptionList from '@/components/app/DescriptionList.vue'
import FormActions from '@/components/app/FormActions.vue'
import LogOutput from '@/components/app/LogOutput.vue'
import PageSection from '@/components/app/PageSection.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { ApiError, api } from '@/lib/api'
import type { Guard } from '@/lib/secure-page'

// vps-server 项目组件: 系统页的"vps-server 版本与升级"卡片(整行). 描述列表: 当前版本, 最新正式版(打开时向 GitHub 查询, 服务器缓存 10 分钟), 安装包类型.
// 有新版本时"升级到 vX"(确认对话框说明控制台会重启), 用本机的安装包类型. 升级在服务器的后台单元里运行, 运行中每 2 秒读一次进度和输出;
// 安装器重启控制台时请求会失败, 卡片显示"正在重启"并每 3 秒重试, 连不上最多等 15 分钟; 回来后显示结果, 版本变了就提示刷新页面载入新界面.
interface Upgrade {
  running: boolean
  version: string
  log: string
  lastExit: number | null
  variant: 'online' | 'offline' | null
  pinned: boolean
}
interface Latest {
  latest: string
  newer: boolean | null
}
type Phase = 'idle' | 'running' | 'restarting' | 'lost' | 'finished'

const POLL_MS = 2000
const RETRY_MS = 3000
const WAIT_MS = 15 * 60 * 1000
const { guard } = defineProps<{ guard: Guard }>()
const { t, te } = useI18n()
const info = ref<Upgrade>()
const latest = ref<Latest>()
const latestError = ref<{ text: string; detail: string } | null>(null)
const checking = ref(false)
const busy = ref(false)
const phase = ref<Phase>('idle')
// 升级开始时的版本: 回来后版本不同就说明升级成功, 需要刷新页面载入新界面
const before = ref('')
// 第一次连不上控制台的时间; 连上后清零
let downSince = 0
let timer: ReturnType<typeof setTimeout> | undefined

const errorText = (code: string) => (te(`vps.upgrade.error.${code}`) ? t(`vps.upgrade.error.${code}`) : undefined)
// 需要重新验证, 重新登录或功能已关闭时交给 guard 处理(切回验证, 转到登录页或说明页)
const handOver = (error: unknown) => guard(() => Promise.reject(error), errorText)

async function load() {
  const value = await guard(() => api<Upgrade>('system/upgrade'))
  if (!value) return
  info.value = value
  // 最新版本只在点"检查更新"时查询: 打开系统页不等 GitHub(国内主机可能很慢)
  if (value.running) follow(value.version)
}

async function check(refresh = false) {
  checking.value = true
  latestError.value = null
  try {
    latest.value = await api<Latest>(`system/upgrade/latest${refresh ? '?refresh=1' : ''}`)
  } catch (error) {
    latest.value = undefined
    if (error instanceof ApiError && error.code.startsWith('latest_')) {
      latestError.value = { text: errorText(error.code) ?? t('vps.common.failed'), detail: typeof error.data.detail === 'string' ? error.data.detail : '' }
    } else {
      await handOver(error)
    }
  } finally {
    checking.value = false
  }
}

function follow(version: string) {
  before.value = version
  downSince = 0
  phase.value = 'running'
  clearTimeout(timer)
  timer = setTimeout(poll, POLL_MS)
}

async function poll() {
  try {
    const value = await api<Upgrade>('system/upgrade')
    downSince = 0
    info.value = value
    if (value.running) {
      phase.value = 'running'
      timer = setTimeout(poll, POLL_MS)
      return
    }
    phase.value = 'finished'
    void check()
  } catch (error) {
    // 连接失败或网关返回 5xx: 安装器正在重启控制台, 等它回来
    const restarting = !(error instanceof ApiError) || error.status >= 500 || error.code === 'request_failed'
    if (!downSince) downSince = Date.now()
    if (!restarting) {
      phase.value = 'idle'
      await handOver(error)
    } else if (Date.now() - downSince > WAIT_MS) {
      phase.value = 'lost'
    } else {
      phase.value = 'restarting'
      timer = setTimeout(poll, RETRY_MS)
    }
  }
}

async function start() {
  busy.value = true
  const version = latest.value?.latest
  const value = await guard(() => api<Upgrade>('system/upgrade', { method: 'POST', body: version ? { version } : {} }), errorText)
  busy.value = false
  if (!value) return
  const running = info.value?.version ?? value.version
  info.value = value
  follow(running)
}

const reload = () => window.location.reload()

onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))

const active = computed(() => ['running', 'restarting'].includes(phase.value))
const changed = computed(() => phase.value === 'finished' && !!info.value && info.value.version !== before.value)
const canUpgrade = computed(() => !!info.value?.pinned && !!latest.value && latest.value.newer !== false && !active.value && !changed.value)
const target = computed(() => latest.value?.latest ?? '')
const variantText = computed(() => t(`vps.upgrade.variant.${info.value?.variant ?? 'unknown'}`))
const items = computed(() => [
  { key: 'current', label: t('vps.upgrade.current'), value: info.value?.version, mono: true },
  { key: 'latest', label: t('vps.upgrade.latest'), value: checking.value ? t('vps.upgrade.checking') : (latest.value?.latest ?? '-'), mono: true },
  { key: 'variant', label: t('vps.upgrade.variantLabel'), value: variantText.value },
])
// 本次升级结束后的结果; 没有在本页升级时只提示上次失败
const result = computed(() => {
  const value = info.value
  if (!value) return null
  if (phase.value === 'finished') {
    if (changed.value) return { tone: 'success' as const, text: t('vps.upgrade.done', { version: value.version }) }
    if (value.lastExit === 0) return { tone: 'info' as const, text: t('vps.upgrade.unchanged') }
    if (value.lastExit == null) return { tone: 'warning' as const, text: t('vps.upgrade.noResult') }
  }
  if ((phase.value === 'finished' || phase.value === 'idle') && value.lastExit != null && value.lastExit !== 0) {
    return { tone: 'destructive' as const, text: t('vps.upgrade.failed', { code: value.lastExit }) }
  }
  return null
})
const showLog = computed(() => !!info.value?.log && (phase.value !== 'idle' || result.value?.tone === 'destructive'))
</script>

<template>
  <PageSection v-if="info" :cols="4" :title="t('vps.upgrade.title')" :description="t('vps.upgrade.description')">
    <DescriptionList :items="items">
      <template #value-latest="{ item }">
        {{ item.value }}
        <StatusBadge v-if="latest && latest.newer === true && !changed" tone="info">{{ t('vps.upgrade.available') }}</StatusBadge>
        <StatusBadge v-else-if="latest && latest.newer === false" tone="success">{{ t('vps.upgrade.upToDate') }}</StatusBadge>
      </template>
    </DescriptionList>
    <AlertBanner v-if="!info.pinned" tone="warning">{{ t('vps.upgrade.notPinned') }}</AlertBanner>
    <AlertBanner v-if="latestError" tone="destructive" :title="latestError.text">{{ latestError.detail || t('vps.upgrade.latestHelp') }}</AlertBanner>
    <AlertBanner v-else-if="latest && latest.newer === null && !active" tone="info">{{ t('vps.upgrade.notRelease') }}</AlertBanner>
    <AlertBanner v-if="phase === 'running'" tone="info">{{ t('vps.upgrade.running') }}</AlertBanner>
    <AlertBanner v-else-if="phase === 'restarting'" tone="info">{{ t('vps.upgrade.restarting') }}</AlertBanner>
    <AlertBanner v-else-if="phase === 'lost'" tone="warning">{{ t('vps.upgrade.lost') }}</AlertBanner>
    <AlertBanner v-else-if="result" :tone="result.tone">{{ result.text }}</AlertBanner>
    <LogOutput v-if="showLog" :text="info.log" :label="t('vps.upgrade.log')" />
    <FormActions>
      <Button variant="outline" :disabled="checking || active" @click="check(true)"><RefreshCw aria-hidden="true" />{{ t('vps.upgrade.check') }}</Button>
      <Button v-if="changed" @click="reload"><RotateCw aria-hidden="true" />{{ t('vps.upgrade.reload') }}</Button>
      <ConfirmDialog
        v-else-if="canUpgrade"
        :title="t('vps.upgrade.upgradeTo', { version: target })"
        :description="t('vps.upgrade.confirm', { version: target, variant: variantText })"
        :confirm-label="t('vps.upgrade.upgradeTo', { version: target })"
        @confirm="start"
      >
        <template #trigger>
          <Button :disabled="busy"><CircleArrowUp aria-hidden="true" />{{ t('vps.upgrade.upgradeTo', { version: target }) }}</Button>
        </template>
      </ConfirmDialog>
    </FormActions>
  </PageSection>
</template>
