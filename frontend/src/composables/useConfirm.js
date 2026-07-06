import { reactive } from 'vue'

/* 全局单例：二次确认对话框状态 */
const state = reactive({ visible: false, message: '' })
let resolver = null

function confirm(message) {
  state.message = message
  state.visible = true
  return new Promise((resolve) => {
    resolver = resolve
  })
}

/* 结束确认：result=true 确定 / false 取消（也用于测试重置状态） */
function settle(result) {
  state.visible = false
  state.message = ''
  if (resolver) {
    resolver(result)
    resolver = null
  }
}

export function useConfirm() {
  return { state, confirm, settle }
}
