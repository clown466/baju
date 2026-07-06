import { reactive } from 'vue'

/* 全局单例：右上角 Toast 通知队列 */
const toasts = reactive([])
let nextId = 1

function push(type, message) {
  const id = nextId++
  toasts.push({ id, type, message })
  setTimeout(() => remove(id), 3000)
}

function remove(id) {
  const i = toasts.findIndex((t) => t.id === id)
  if (i !== -1) toasts.splice(i, 1)
}

export function useToast() {
  return {
    toasts,
    success: (message) => push('success', message),
    error: (message) => push('error', message),
    remove,
  }
}
