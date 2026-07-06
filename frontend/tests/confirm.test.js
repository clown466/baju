import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, test } from 'vitest'
import ConfirmDialog from '../src/components/ConfirmDialog.vue'
import { useConfirm } from '../src/composables/useConfirm'

beforeEach(() => {
  // 清理模块级单例状态，避免用例间互相影响
  useConfirm().settle(false)
})

function button(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

test('confirm() 弹出遮罩与 message', async () => {
  const wrapper = mount(ConfirmDialog)
  expect(wrapper.find('.confirm-mask').exists()).toBe(false)
  useConfirm().confirm('确定删除？')
  await flushPromises()
  expect(wrapper.find('.confirm-mask').exists()).toBe(true)
  expect(wrapper.text()).toContain('确定删除？')
})

test('点「确定」resolve true 且遮罩消失', async () => {
  const wrapper = mount(ConfirmDialog)
  const p = useConfirm().confirm('继续吗？')
  await flushPromises()
  const ok = button(wrapper, '确定')
  expect(ok.classes()).toContain('danger')
  await ok.trigger('click')
  await expect(p).resolves.toBe(true)
  expect(wrapper.find('.confirm-mask').exists()).toBe(false)
})

test('点「取消」resolve false 且遮罩消失', async () => {
  const wrapper = mount(ConfirmDialog)
  const p = useConfirm().confirm('继续吗？')
  await flushPromises()
  await button(wrapper, '取消').trigger('click')
  await expect(p).resolves.toBe(false)
  expect(wrapper.find('.confirm-mask').exists()).toBe(false)
})
