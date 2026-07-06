import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, test } from 'vitest'
import EditorPane from '../src/components/EditorPane.vue'
import MarkdownView from '../src/components/MarkdownView.vue'
import { useConfirm } from '../src/composables/useConfirm'

beforeEach(() => {
  useConfirm().settle(false) // 清理确认框单例状态
})

function button(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

test('MarkdownView 渲染 Markdown', () => {
  const wrapper = mount(MarkdownView, { props: { content: '**加粗**' } })
  expect(wrapper.html()).toContain('<strong>加粗</strong>')
})

test('MarkdownView 过滤脚本注入', () => {
  const wrapper = mount(MarkdownView, {
    props: { content: '<script>alert(1)</' + 'script>正文' },
  })
  expect(wrapper.html()).not.toContain('<script>')
  expect(wrapper.text()).toContain('正文')
})

test('EditorPane 查看态渲染内容，编辑后保存 emit', async () => {
  const wrapper = mount(EditorPane, { props: { content: '# 标题' } })
  expect(wrapper.html()).toContain('<h1>标题</h1>')
  await wrapper.findAll('button').find((b) => b.text() === '编辑').trigger('click')
  await wrapper.find('textarea').setValue('新内容')
  await wrapper.findAll('button').find((b) => b.text() === '保存').trigger('click')
  expect(wrapper.emitted('save')[0]).toEqual(['新内容'])
  expect(wrapper.find('textarea').exists()).toBe(false)
})

test('EditorPane markdown=false 用纯文本渲染', () => {
  const wrapper = mount(EditorPane, { props: { content: '1-1 日 内 客厅', markdown: false } })
  expect(wrapper.find('pre.plain').text()).toContain('1-1 日 内 客厅')
})

test('EditorPane 有未保存修改时取消编辑弹确认，确定才退出', async () => {
  const wrapper = mount(EditorPane, { props: { content: '原文' } })
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('textarea').setValue('改动后')
  await button(wrapper, '取消编辑').trigger('click')
  expect(useConfirm().state.visible).toBe(true)
  expect(useConfirm().state.message).toContain('未保存')
  // 取消放弃 → 仍在编辑态
  useConfirm().settle(false)
  await flushPromises()
  expect(wrapper.find('textarea').exists()).toBe(true)
  // 再次取消编辑并确认 → 退出编辑态
  await button(wrapper, '取消编辑').trigger('click')
  useConfirm().settle(true)
  await flushPromises()
  expect(wrapper.find('textarea').exists()).toBe(false)
})

test('EditorPane 无修改时取消编辑直接退出不弹确认', async () => {
  const wrapper = mount(EditorPane, { props: { content: '原文' } })
  await button(wrapper, '编辑').trigger('click')
  await button(wrapper, '取消编辑').trigger('click')
  expect(useConfirm().state.visible).toBe(false)
  await flushPromises()
  expect(wrapper.find('textarea').exists()).toBe(false)
})
