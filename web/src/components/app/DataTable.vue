<script setup lang="ts" generic="Row extends Record<string, unknown>">
import { ArrowDown, ArrowUp, ArrowUpDown } from '@lucide/vue'
import { CheckboxIndicator, CheckboxRoot } from 'reka-ui'
import { Check } from '@lucide/vue'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

// 数据表: 放在整行卡片里, 行数多时用 PaginationBar 分页(超过 10 行**必须**分页). 表头底色, 行分隔线, 数字列右对齐等宽数字; 窄屏时在自身区域内水平滚动. 替代原生 <table>.
// 自定义单元格用插槽 cell-<key>, 参数 { row, value }. 没有数据时显示 empty 文本.
// 列设 sortable 后点表头排序(升序, 降序, 取消循环), 排序在组件内对 rows 进行; selectable 时第一列是勾选框, 表头勾选框全选, v-model:selected 是选中行的 rowKey 数组.
const props = defineProps<{
  columns: { key: string; label: string; align?: 'start' | 'end'; mono?: boolean; sortable?: boolean }[]
  rows: Row[]
  rowKey: keyof Row
  caption: string
  empty: string
  selectable?: boolean
}>()
const selected = defineModel<unknown[]>('selected', { default: () => [] })
const { t } = useI18n()

const sort = ref<{ key: string; dir: 'asc' | 'desc' } | null>(null)
function toggleSort(key: string) {
  if (sort.value?.key !== key) sort.value = { key, dir: 'asc' }
  else if (sort.value.dir === 'asc') sort.value = { key, dir: 'desc' }
  else sort.value = null
}
const sorted = computed(() => {
  const current = sort.value
  if (!current) return props.rows
  const factor = current.dir === 'asc' ? 1 : -1
  return [...props.rows].sort((a, b) => {
    const x = a[current.key]
    const y = b[current.key]
    return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))) * factor
  })
})
const allSelected = computed(() => props.rows.length > 0 && props.rows.every((row) => selected.value.includes(row[props.rowKey])))
const someSelected = computed(() => !allSelected.value && props.rows.some((row) => selected.value.includes(row[props.rowKey])))
function toggleAll(value: boolean | 'indeterminate') {
  selected.value = value === true ? props.rows.map((row) => row[props.rowKey]) : []
}
function toggleRow(row: Row, value: boolean | 'indeterminate') {
  const key = row[props.rowKey]
  selected.value = value === true ? [...selected.value, key] : selected.value.filter((item) => item !== key)
}
const boxClass =
  'flex size-6 shrink-0 items-center justify-center rounded-sm outline-none group'
</script>

<template>
  <div data-control class="overflow-x-auto rounded-md border border-border">
    <table class="w-full border-collapse text-sm">
      <caption class="sr-only">{{ caption }}</caption>
      <thead class="bg-muted">
        <tr>
          <th v-if="selectable" scope="col" class="h-10 w-10 px-2">
            <CheckboxRoot :model-value="allSelected ? true : someSelected ? 'indeterminate' : false" :aria-label="t('component.selectAll')" :class="boxClass" @update:model-value="toggleAll">
              <span class="flex size-4 items-center justify-center rounded-sm border border-input bg-card text-primary-foreground group-data-[state=checked]:border-primary group-data-[state=checked]:bg-primary group-data-[state=indeterminate]:border-primary group-data-[state=indeterminate]:bg-primary">
                <CheckboxIndicator><Check class="size-3" aria-hidden="true" /></CheckboxIndicator>
              </span>
            </CheckboxRoot>
          </th>
          <th
            v-for="column in columns"
            :key="column.key"
            scope="col"
            :aria-sort="sort?.key === column.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : column.sortable ? 'none' : undefined"
            class="h-10 px-2 font-medium whitespace-nowrap text-muted-foreground"
            :class="column.align === 'end' ? 'text-right' : 'text-left'"
          >
            <button
              v-if="column.sortable"
              type="button"
              class="inline-flex h-6 items-center gap-1 rounded-sm hover:text-foreground"
              :aria-label="t('component.sortBy', { column: column.label })"
              @click="toggleSort(column.key)"
            >
              {{ column.label }}
              <ArrowUp v-if="sort?.key === column.key && sort.dir === 'asc'" class="size-4" aria-hidden="true" />
              <ArrowDown v-else-if="sort?.key === column.key" class="size-4" aria-hidden="true" />
              <ArrowUpDown v-else class="size-4 opacity-50" aria-hidden="true" />
            </button>
            <template v-else>{{ column.label }}</template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in sorted" :key="String(row[rowKey])" class="border-t border-border" :class="selected.includes(row[rowKey]) && 'bg-accent'">
          <td v-if="selectable" class="h-12 w-10 px-2">
            <CheckboxRoot :model-value="selected.includes(row[rowKey])" :aria-label="t('component.selectRow', { name: String(row[rowKey]) })" :class="boxClass" @update:model-value="(value) => toggleRow(row, value)">
              <span class="flex size-4 items-center justify-center rounded-sm border border-input bg-card text-primary-foreground group-data-[state=checked]:border-primary group-data-[state=checked]:bg-primary">
                <CheckboxIndicator><Check class="size-3" aria-hidden="true" /></CheckboxIndicator>
              </span>
            </CheckboxRoot>
          </td>
          <td
            v-for="column in columns"
            :key="column.key"
            class="h-12 px-2"
            :class="[column.align === 'end' ? 'text-right tabular-nums' : 'text-left', column.mono ? 'font-mono' : '']"
          >
            <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">{{ row[column.key] }}</slot>
          </td>
        </tr>
        <tr v-if="!rows.length" class="border-t border-border">
          <td :colspan="columns.length + (selectable ? 1 : 0)" class="h-24 px-3 text-center text-muted-foreground">{{ empty }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
