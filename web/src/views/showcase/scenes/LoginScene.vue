<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import LoginPanel from '@/components/app/LoginPanel.vue'
import PageHeader from '@/components/app/PageHeader.vue'

// 场景: 登录页. 与真实登录页(LoginView)共用登录卡 LoginPanel: 居中的一张卡片, 这里是静态示例, 不登录.
const { t } = useI18n()
const trail = computed(() => [{ to: '/scenes', label: t('page.showcaseScenes') }])
const password = ref('')
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseScenesLogin')" :description="t('showcase.scenes.desc.login')" :trail="trail" />
    <LoginPanel v-model="password" :can-submit="!!password" />
  </CardGrid>
</template>
