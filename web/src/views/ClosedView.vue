<script setup lang="ts">
import { CircleOff } from '@lucide/vue'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import CardGrid from '@/components/app/CardGrid.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import LoadingState from '@/components/app/LoadingState.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { errorText } from '@/lib/errors'
import { showToast } from '@/lib/toast'

// 功能已关闭: 在主页关掉的功能, 打开它的页面时显示这里. 功能已经重新打开时直接去功能页.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const name = ref('')
// 地址里没有或是不认识的模块: 只显示"页面已关闭"
const unknown = ref(false)

onMounted(async () => {
  const module = typeof route.query.module === 'string' ? route.query.module : ''
  try {
    const data = await api<{ name: string; closed: boolean; destination: string }>(`closed?module=${encodeURIComponent(module)}`)
    if (!data.closed) {
      // 公开页面(/public/*)由服务器转到对外地址, 整页跳转; 其他是单页里的页面
      if (data.destination.startsWith('/public/')) window.location.replace(data.destination)
      else await router.replace(data.destination)
      return
    }
    name.value = data.name
  } catch (err) {
    if (isSignedOut(err)) return
    if (err instanceof ApiError && err.status === 404) unknown.value = true
    else showToast(errorText(err), 'destructive')
  }
})
</script>

<template>
  <CardGrid>
    <PageHeader :title="name || t('console.module_closed_title')" />
    <PageSection v-if="!name && !unknown" :cols="4">
      <LoadingState />
    </PageSection>
    <PageSection v-else :cols="4" :title="t('console.module_closed_title')">
      <EmptyState :icon="CircleOff" :title="t('console.module_closed_title')" :description="unknown ? undefined : t('vps.closed.description', { name })" />
    </PageSection>
  </CardGrid>
</template>
