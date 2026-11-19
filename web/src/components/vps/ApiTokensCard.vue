<script setup lang="ts">
import { KeyRound, Trash2 } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AlertBanner from '@/components/app/AlertBanner.vue'
import CardForm from '@/components/app/CardForm.vue'
import ConfirmDialog from '@/components/app/ConfirmDialog.vue'
import CopyField from '@/components/app/CopyField.vue'
import DataTable from '@/components/app/DataTable.vue'
import FormActions from '@/components/app/FormActions.vue'
import FormField from '@/components/app/FormField.vue'
import PageSection from '@/components/app/PageSection.vue'
import SegmentedControl from '@/components/app/SegmentedControl.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, api, isSignedOut } from '@/lib/api'
import { showToast } from '@/lib/toast'

// vps-server 项目组件: 集中管理页的 API 令牌卡片(整行, 表单样式). 上面是已有令牌的表格(名称, 权限, 前后几位, 最近使用), 每行可删除;
// 下面填名称, 选只读或读写后生成. 令牌只在生成后显示这一次(CopyField), 服务器只保存它的哈希. 用法见 doc/API.md.
interface Token { id: string; name: string; scope: 'read' | 'write'; hint: string; created: number; lastUsed: number | null; lastIp: string | null }
const emit = defineEmits<{ expired: [] }>()
const { t, locale } = useI18n()
const tokens = ref<Token[]>([])
const name = ref('')
const scope = ref<'read' | 'write'>('read')
const created = ref('')
const error = ref('')
const busy = ref(false)

async function call<T>(path: string, body?: unknown): Promise<T | undefined> {
  busy.value = true
  try {
    return await api<T>(path, body === undefined ? {} : { method: 'POST', body })
  } catch (err) {
    if (err instanceof ApiError && err.code === 'security_required') emit('expired')
    else if (!isSignedOut(err)) error.value = err instanceof ApiError && err.code === 'too_many' ? t('vps.tokens.tooMany') : err instanceof ApiError && err.code === 'name_invalid' ? t('vps.tokens.nameInvalid') : t('vps.common.failed')
    return undefined
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  const value = await call<{ tokens: Token[] }>('security/tokens')
  if (value) tokens.value = value.tokens
})

const scopes = computed(() => [
  { value: 'read' as const, label: t('vps.tokens.read') },
  { value: 'write' as const, label: t('vps.tokens.write') },
])
const time = (value: number | null) => (value ? new Date(value * 1000).toLocaleString(locale.value, { dateStyle: 'short', timeStyle: 'short' }) : '')
const rows = computed(() =>
  tokens.value.map((row) => ({
    ...row,
    scopeText: t(`vps.tokens.${row.scope}`),
    usedText: row.lastUsed ? `${time(row.lastUsed)} · ${row.lastIp ?? ''}` : '',
  })),
)
const columns = computed(() => [
  { key: 'name', label: t('vps.tokens.name') },
  { key: 'scopeText', label: t('vps.tokens.scope') },
  { key: 'hint', label: t('vps.tokens.hint'), mono: true },
  { key: 'usedText', label: t('vps.tokens.lastUsed'), mono: true },
  { key: 'action', label: t('security.actions'), align: 'end' as const },
])

async function create() {
  error.value = ''
  created.value = ''
  const value = await call<{ token: string; tokens: Token[] }>('security/tokens', { name: name.value, scope: scope.value })
  if (!value) return
  tokens.value = value.tokens
  created.value = value.token
  name.value = ''
  showToast(t('vps.tokens.created'), 'success')
}
async function remove(id: string) {
  const value = await call<{ tokens: Token[] }>('security/tokens/delete', { id })
  if (value) {
    tokens.value = value.tokens
    showToast(t('vps.tokens.deleted'), 'success')
  }
}
</script>

<template>
  <CardForm @submit.prevent="create">
    <PageSection :cols="4" :title="t('vps.tokens.title')" :description="t('vps.tokens.description')">
      <DataTable :columns="columns" :rows="rows" row-key="id" :caption="t('vps.tokens.title')" :empty="t('vps.tokens.empty')">
        <template #cell-action="{ row }">
          <ConfirmDialog
            :title="t('vps.tokens.deleteTitle', { name: String(row.name) })"
            :description="t('vps.tokens.deleteDescription')"
            :confirm-label="t('vps.security.delete')"
            danger
            @confirm="remove(String(row.id))"
          >
            <template #trigger>
              <Button type="button" variant="outline" size="sm" :disabled="busy"><Trash2 aria-hidden="true" />{{ t('vps.security.delete') }}</Button>
            </template>
          </ConfirmDialog>
        </template>
      </DataTable>
      <AlertBanner v-if="created" tone="success">{{ t('vps.tokens.showOnce') }}</AlertBanner>
      <FormField v-if="created" v-slot="field" :label="t('vps.tokens.newToken')">
        <CopyField :id="field.id" :value="created" />
      </FormField>
      <FormField v-slot="field" :label="t('vps.tokens.name')" :error="error" :span="8">
        <Input :id="field.id" v-model.trim="name" maxlength="40" autocomplete="off" :aria-invalid="field.invalid" :aria-describedby="field.describedby" />
      </FormField>
      <FormField :label="t('vps.tokens.scope')" group :span="4">
        <SegmentedControl v-model="scope" :options="scopes" :label="t('vps.tokens.scope')" />
      </FormField>
      <FormActions>
        <Button type="submit" :disabled="busy || !name"><KeyRound aria-hidden="true" />{{ t('vps.tokens.create') }}</Button>
      </FormActions>
    </PageSection>
  </CardForm>
</template>
