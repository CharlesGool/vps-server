import { onBeforeUnmount, onMounted, ref, type Ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

// 未保存修改的离开保护: 表单有未保存的修改(dirty)时, 站内跳转先弹出 ConfirmDialog(open 绑定 guard.open, @confirm 绑定 guard.confirm),
// 点取消留在当前页; 刷新或关闭标签页时由浏览器提示. 保存成功后把 dirty 置回 false.
export function useUnsavedGuard(dirty: Ref<boolean>) {
  const open = ref(false)
  let resolve: ((leave: boolean) => void) | null = null

  onBeforeRouteLeave(() => {
    if (!dirty.value) return true
    open.value = true
    return new Promise<boolean>((done) => (resolve = done))
  })
  // 对话框关闭但没点确认, 等于取消
  watch(open, (value) => {
    if (!value && resolve) {
      resolve(false)
      resolve = null
    }
  })
  function confirm() {
    resolve?.(true)
    resolve = null
  }

  const warn = (event: BeforeUnloadEvent) => {
    if (dirty.value) event.preventDefault()
  }
  onMounted(() => window.addEventListener('beforeunload', warn))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', warn))
  return { open, confirm }
}
