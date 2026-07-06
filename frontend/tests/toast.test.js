import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import Toast from '../src/components/Toast.vue'
import { useToast } from '../src/composables/useToast'

beforeEach(() => {
  vi.useFakeTimers()
  useToast().toasts.splice(0)
})
afterEach(() => {
  vi.useRealTimers()
})

test('success() 后容器出现文案且带 .toast.success', async () => {
  const wrapper = mount(Toast)
  useToast().success('已保存')
  await flushPromises()
  expect(wrapper.find('.toast-container').exists()).toBe(true)
  const toast = wrapper.find('.toast.success')
  expect(toast.exists()).toBe(true)
  expect(toast.text()).toContain('已保存')
})

test('3 秒后自动消失', async () => {
  const wrapper = mount(Toast)
  useToast().success('稍纵即逝')
  await flushPromises()
  expect(wrapper.find('.toast').exists()).toBe(true)
  vi.advanceTimersByTime(3000)
  await flushPromises()
  expect(wrapper.find('.toast').exists()).toBe(false)
})

test('error() 渲染 .toast.error', async () => {
  const wrapper = mount(Toast)
  useToast().error('出错了')
  await flushPromises()
  const toast = wrapper.find('.toast.error')
  expect(toast.exists()).toBe(true)
  expect(toast.text()).toContain('出错了')
})

test('点击 toast 立即关闭', async () => {
  const wrapper = mount(Toast)
  useToast().success('点我关闭')
  await flushPromises()
  await wrapper.find('.toast').trigger('click')
  expect(wrapper.find('.toast').exists()).toBe(false)
})
