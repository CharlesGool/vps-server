<script setup lang="ts">
import { File as FileIcon, Trash2, Upload } from '@lucide/vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

// 文件上传: 虚线框可点击选择也可拖放文件, 下面是已选文件的列表(名称, 大小, 移除). 只负责选择和校验, 真正上传由页面做.
// accept 是允许的类型(如 ".pdf,image/*"), maxSize 是单个文件最大字节数, multiple 允许多个. 不合格的文件不加入列表, 在下面用红字说明原因.
// 选择区的无障碍名称就是它的可见文字; label 是已选文件列表的名称(给读屏).
const props = defineProps<{ accept?: string; maxSize?: number; multiple?: boolean; label: string }>()
const files = defineModel<File[]>({ default: () => [] })
const { t } = useI18n()
const input = ref<HTMLInputElement>()
const dragging = ref(false)
const errors = ref<string[]>([])

const format = (bytes: number) => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : bytes >= 1024 ? `${Math.round(bytes / 1024)} KB` : `${bytes} B`)
function allowed(file: File) {
  if (!props.accept) return true
  return props.accept.split(',').some((rule) => {
    const item = rule.trim().toLowerCase()
    return item.startsWith('.') ? file.name.toLowerCase().endsWith(item) : item.endsWith('/*') ? file.type.startsWith(item.slice(0, -1)) : file.type === item
  })
}
function add(list: FileList | null) {
  errors.value = []
  const accepted: File[] = []
  for (const file of list ?? []) {
    if (!allowed(file)) errors.value.push(t('component.fileType', { name: file.name }))
    else if (props.maxSize && file.size > props.maxSize) errors.value.push(t('component.fileTooLarge', { name: file.name, max: format(props.maxSize) }))
    else accepted.push(file)
  }
  files.value = props.multiple ? [...files.value, ...accepted] : accepted.slice(0, 1)
  if (input.value) input.value.value = ''
}
function onDrop(event: DragEvent) {
  dragging.value = false
  add(event.dataTransfer?.files ?? null)
}
</script>

<template>
  <div data-control class="flex flex-col gap-2">
    <button
      type="button"
      class="flex w-full flex-col items-center gap-2 rounded-md border border-dashed border-input px-3 py-6 text-center text-sm transition-colors hover:bg-accent"
      :class="dragging ? 'bg-accent' : 'bg-muted'"
      @click="input?.click()"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
    >
      <Upload class="size-5 text-muted-foreground" aria-hidden="true" />
      <span class="font-medium">{{ t('component.dropFiles') }}</span>
      <span v-if="maxSize || accept" class="text-muted-foreground">{{ [accept, maxSize ? `≤ ${format(maxSize)}` : ''].filter(Boolean).join(' · ') }}</span>
    </button>
    <input ref="input" type="file" class="sr-only" tabindex="-1" aria-hidden="true" :accept="accept" :multiple="multiple" @change="add(($event.target as HTMLInputElement).files)" />
    <ul v-if="files.length" :aria-label="label" class="flex flex-col gap-1">
      <li v-for="(file, index) in files" :key="`${file.name}-${index}`" class="flex h-10 items-center gap-2 rounded-md border border-border px-2 text-sm">
        <FileIcon class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span class="min-w-0 flex-1 truncate">{{ file.name }}</span>
        <span class="shrink-0 text-muted-foreground tabular-nums">{{ format(file.size) }}</span>
        <Button variant="outline" size="icon-sm" class="w-8" :aria-label="t('component.removeFile', { name: file.name })" @click="files = files.filter((_, i) => i !== index)">
          <Trash2 aria-hidden="true" />
        </Button>
      </li>
    </ul>
    <p v-for="error in errors" :key="error" role="alert" class="text-sm text-destructive">{{ error }}</p>
  </div>
</template>
