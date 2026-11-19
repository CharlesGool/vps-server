<script setup lang="ts">
import { ChevronRight, File, Folder, FolderOpen } from '@lucide/vue'
import { TreeItem, TreeRoot } from 'reka-ui'
import { type BlockLayout, blockAttrs } from './cardLayout'

// 树形列表: 有层级的数据(目录, 组织结构). 每行高 40 px, 每深一层缩进 16 px; 有子项的行左侧是箭头, 点击行展开或收起, 方向键移动, 回车选中.
// v-model 是选中的节点(单选). 层级超过 4 层或项目很多时改用表格加筛选. label 是整棵树的名称(给读屏).
export interface TreeNode {
  id: string
  label: string
  children?: TreeNode[]
}
const props = defineProps<{ items: TreeNode[]; label: string; defaultExpanded?: string[] } & BlockLayout>()
const selected = defineModel<TreeNode>()
</script>

<template>
  <TreeRoot
    v-slot="{ flattenItems }"
    v-model="selected"
    v-bind="blockAttrs(props)"
    :items="items"
    :get-key="(item: TreeNode) => item.id"
    :default-expanded="defaultExpanded"
    :aria-label="label"
    data-tree
    class="flex flex-col rounded-md border border-border p-1"
  >
    <TreeItem
      v-for="item in flattenItems"
      v-slot="{ isExpanded, isSelected }"
      :key="item._id"
      v-bind="item.bind"
      class="flex h-10 cursor-pointer items-center gap-2 rounded-sm px-2 text-sm outline-none select-none hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring data-selected:bg-accent data-selected:font-medium data-selected:text-accent-foreground"
    >
      <span v-for="level in item.level - 1" :key="level" class="w-4 shrink-0" />
      <ChevronRight v-if="item.hasChildren" class="size-4 shrink-0 text-muted-foreground transition-transform" :class="isExpanded && 'rotate-90'" aria-hidden="true" />
      <span v-else class="w-4 shrink-0" />
      <component :is="item.hasChildren ? (isExpanded ? FolderOpen : Folder) : File" class="size-4 shrink-0" :class="isSelected ? 'text-primary' : 'text-muted-foreground'" aria-hidden="true" />
      <span class="truncate">{{ item.value.label }}</span>
    </TreeItem>
  </TreeRoot>
</template>
