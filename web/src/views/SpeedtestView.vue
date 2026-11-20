<script setup lang="ts">
import { Gauge } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import FormActions from '@/components/app/FormActions.vue'
import GroupBlock from '@/components/app/GroupBlock.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import TrafficCard from '@/components/vps/TrafficCard.vue'
import { Button } from '@/components/ui/button'
import { api, isSignedOut } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { loadSpeedtest, type Speedtest } from '@/lib/librespeed'
import { showToast } from '@/lib/toast'

// 浏览器测速: 一张整行卡片, 延迟, 抖动, 下载, 上传四组并排(窄屏上下排), 下面是开始按钮; 再下面是测速的流量卡片.
const { t } = useI18n()
const clientIp = ref('')
const config = ref<Record<string, unknown>>()

type Key = 'latency' | 'jitter' | 'download' | 'upload'
type Phase = 'waiting' | 'measuring' | 'done' | 'failed'
const METRICS: { key: Key; unit: string }[] = [
  { key: 'latency', unit: 'ms' },
  { key: 'jitter', unit: 'ms' },
  { key: 'download', unit: 'Mbps' },
  { key: 'upload', unit: 'Mbps' },
]
const blank = () => ({ value: '', phase: 'waiting' as Phase })
const results = ref<Record<Key, { value: string; phase: Phase }>>({ latency: blank(), jitter: blank(), download: blank(), upload: blank() })
const running = ref(false)
let test: Speedtest | undefined

onMounted(async () => {
  try {
    const data = await api<{ clientIp: string; config: Record<string, unknown> }>('speedtest')
    clientIp.value = data.clientIp
    config.value = data.config
  } catch (err) {
    if (!isSignedOut(err)) showToast(errorText(err), 'destructive')
  }
})
onBeforeUnmount(() => {
  try {
    test?.abort()
  } catch {
    // 还没开始或已经结束
  }
})

// LibreSpeed 的状态值: 空串表示还没有数据, "Fail" 表示这一项失败
function show(key: Key, status: string, active: boolean, digits: number) {
  if (status === '') return
  if (status === 'Fail') {
    results.value[key] = { value: '', phase: 'failed' }
    return
  }
  const number = Number.parseFloat(status)
  if (Number.isNaN(number)) return
  results.value[key] = { value: number.toFixed(digits), phase: active ? 'measuring' : 'done' }
}

async function run() {
  if (running.value || !config.value) return
  running.value = true
  results.value = { latency: blank(), jitter: blank(), download: blank(), upload: blank() }
  try {
    const Engine = await loadSpeedtest()
    test = new Engine()
    for (const [name, value] of Object.entries(config.value)) test.setParameter(name, value)
    test.onupdate = (data) => {
      show('download', data.dlStatus, data.testState === 1, 2)
      show('upload', data.ulStatus, data.testState === 3, 2)
      show('latency', data.pingStatus, data.testState === 2, 1)
      if (data.jitterStatus !== 'Fail') show('jitter', data.jitterStatus, data.testState === 2, 1)
    }
    test.onend = () => {
      running.value = false
    }
    test.start()
  } catch {
    running.value = false
    showToast(t('vps.common.failed'), 'destructive')
  }
}

const description = computed(() => (clientIp.value ? `${t('console.your_ip')}: ${clientIp.value}` : undefined))
const PHASES: Record<Phase, string> = {
  waiting: 'console.waiting',
  measuring: 'console.measuring',
  done: 'console.done',
  failed: 'vps.speedtest.failed',
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('console.speedtest')" :description="description" />

    <PageSection :cols="4" :title="t('vps.speedtest.result')">
      <!-- 每组: 名称, 大号数值和单位, 状态; 测速中的数值变化用 aria-live 播报 -->
      <GroupBlock v-for="metric in METRICS" :key="metric.key" :title="t(`console.${metric.key}`)" :span="3">
        <p class="text-3xl font-semibold tabular-nums" aria-live="polite">
          {{ results[metric.key].value || t('console.idle') }}
          <span class="text-sm font-normal text-muted-foreground">{{ metric.unit }}</span>
        </p>
        <p class="text-sm" :class="results[metric.key].phase === 'failed' ? 'text-destructive' : 'text-muted-foreground'">
          {{ t(PHASES[results[metric.key].phase]) }}
        </p>
      </GroupBlock>
      <FormActions>
        <Button :disabled="running || !config" @click="run">
          <Gauge aria-hidden="true" />{{ running ? t('console.running') : t('console.run_test') }}
        </Button>
      </FormActions>
    </PageSection>

    <TrafficCard feature="speedtest" />
  </CardGrid>
</template>
