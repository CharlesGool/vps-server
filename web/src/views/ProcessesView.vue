<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import AdminVerify from '@/components/vps/AdminVerify.vue'
import ProcessesCard from '@/components/vps/ProcessesCard.vue'
import { useSecurePage } from '@/lib/secure-page'

// 进程: 列表模式, 一张整行卡片(ProcessesCard). 进入前要验证管理员密码(和终端相同); 验证后重新挂载卡片, 让它重新读取.
const { t } = useI18n()
const { state, guard } = useSecurePage()
const round = ref(0)
function verified() {
  state.value = 'loading'
  round.value += 1
}
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('vps.processes.title')" :description="t('vps.processes.description')" />
    <AdminVerify v-if="state === 'verify' || state === 'ip'" :ip-only="state === 'ip'" @verified="verified" />
    <ProcessesCard v-else :key="round" :guard="guard" />
  </CardGrid>
</template>
