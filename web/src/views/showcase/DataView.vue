<script setup lang="ts">
import { Inbox } from '@lucide/vue'
import { computed, ref } from 'vue'
import ActionMenu from '@/components/app/ActionMenu.vue'
import AlertBanner from '@/components/app/AlertBanner.vue'
import PaginationBar from '@/components/app/PaginationBar.vue'
import StatusBadge from '@/components/app/StatusBadge.vue'
import { useI18n } from 'vue-i18n'
import CardGrid from '@/components/app/CardGrid.vue'
import DataTable from '@/components/app/DataTable.vue'
import EmptyState from '@/components/app/EmptyState.vue'
import InfoTip from '@/components/app/InfoTip.vue'
import PageHeader from '@/components/app/PageHeader.vue'
import PageSection from '@/components/app/PageSection.vue'
import TreeList, { type TreeNode } from '@/components/app/TreeList.vue'
import UnderlineTabs from '@/components/app/UnderlineTabs.vue'
import UserAvatar from '@/components/app/UserAvatar.vue'

// 组件样例: 数据展示. 数据表放进整行卡片, 超过一页时分页; 树形列表和成员表并排各占 2 列.
const { t } = useI18n()
const trail = computed(() => [{ to: '/showcase', label: t('page.showcase') }])
const tab = ref('one')
const columns = computed(() => [
  { key: 'name', label: t('showcase.table.name'), sortable: true },
  { key: 'address', label: t('showcase.table.address'), mono: true },
  { key: 'requests', label: t('showcase.table.requests'), align: 'end' as const, sortable: true },
  { key: 'status', label: t('showcase.table.status') },
  { key: 'actions', label: t('security.actions'), align: 'end' as const },
])
const all = Array.from({ length: 12 }, (_, i) => ({ id: i + 1, name: `host-${i + 1}`, address: `192.168.1.${20 + i}`, requests: ((i * 7919) % 1700) + 40 }))
const menuItems = computed(() => [
  { key: 'edit', label: t('showcase.overlays.edit') },
  { key: 'remove', label: t('showcase.overlays.remove'), danger: true },
])
// 树形列表: 有层级的数据; 成员表: 名字列带头像
const tree = computed<TreeNode[]>(() => [
  {
    id: 'web',
    label: 'web',
    children: [
      { id: 'src', label: 'src', children: [{ id: 'main', label: 'main.ts' }, { id: 'app', label: 'App.vue' }, { id: 'router', label: 'router.ts' }] },
      { id: 'pkg', label: 'package.json' },
    ],
  },
  { id: 'cmd', label: 'cmd', children: [{ id: 'server', label: 'server', children: [{ id: 'gomain', label: 'main.go' }] }] },
  { id: 'readme', label: 'README.md' },
])
const file = ref<TreeNode>()
const memberColumns = computed(() => [
  { key: 'name', label: t('showcase.members.name') },
  { key: 'role', label: t('showcase.members.role') },
])
const members = computed(() => [
  { id: 1, name: 'Ada Lovelace', role: t('showcase.members.owner') },
  { id: 2, name: '王小明', role: t('showcase.members.admin') },
  { id: 3, name: 'Grace Hopper', role: t('showcase.members.member') },
  { id: 4, name: 'Linus Torvalds', role: t('showcase.members.member') },
  { id: 5, name: '李华', role: t('showcase.members.viewer') },
])
const PAGE_SIZE = 5
const page = ref(1)
const selected = ref<unknown[]>([])
const pageRows = computed(() => all.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))
</script>

<template>
  <CardGrid>
    <PageHeader :title="t('page.showcaseData')" :description="t('showcase.desc.data')" :trail="trail" />
    <!-- 数据表: 可排序(点表头), 可多选, 超过 5 行分页; 状态用 StatusBadge -->
    <PageSection :cols="4" :title="t('showcase.table.selectable')">
      <AlertBanner v-if="selected.length" tone="info">{{ t('component.selectedCount', { count: selected.length }) }}</AlertBanner>
      <DataTable v-model:selected="selected" selectable :columns="columns" :rows="pageRows" row-key="id" :caption="t('showcase.table.title')" :empty="t('showcase.empty')">
        <template #cell-actions="{ row }">
          <ActionMenu icon-only :label="`${t('component.moreActions')} ${row.name}`" :items="menuItems" />
        </template>
        <template #cell-status="{ row }">
          <StatusBadge :tone="row.requests > 1000 ? 'warning' : 'success'">{{ t(row.requests > 1000 ? 'showcase.feedback.pending' : 'showcase.feedback.running') }}</StatusBadge>
        </template>
      </DataTable>
      <PaginationBar v-model="page" :total="all.length" :page-size="PAGE_SIZE" />
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.tree.title')" :description="file ? t('showcase.tree.selected', { name: file.label }) : t('showcase.tree.hint')">
      <TreeList v-model="file" :items="tree" :label="t('showcase.tree.title')" :default-expanded="['web', 'src']" />
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.members.title')">
      <DataTable :columns="memberColumns" :rows="members" row-key="id" :caption="t('showcase.members.title')" :empty="t('showcase.empty')">
        <template #cell-name="{ row }">
          <UserAvatar :name="String(row.name)" show-name />
        </template>
      </DataTable>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.tabs')">
      <template #info>
        <InfoTip :label="t('showcase.infoLabel')" :text="t('showcase.info')" />
      </template>
      <UnderlineTabs
        v-model="tab"
        :label="t('showcase.tabs')"
        :tabs="[
          { value: 'one', label: t('showcase.tabOne') },
          { value: 'two', label: t('showcase.tabTwo') },
        ]"
      >
        <template #default="{ active }">
          <p class="text-muted-foreground">{{ t(`showcase.panel.${active}`) }}</p>
        </template>
      </UnderlineTabs>
    </PageSection>
    <PageSection :cols="2" :title="t('showcase.empty')">
      <EmptyState :icon="Inbox" :title="t('showcase.empty')" :description="t('showcase.emptyDescription')" />
    </PageSection>
  </CardGrid>
</template>
