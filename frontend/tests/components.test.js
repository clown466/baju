import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import EditorPane from '../src/components/EditorPane.vue'
import MarkdownView from '../src/components/MarkdownView.vue'

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
