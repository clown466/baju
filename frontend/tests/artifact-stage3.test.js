import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import ArtifactTab from '../src/tabs/ArtifactTab.vue'
import Stage3Settings from '../src/tabs/Stage3Settings.vue'

vi.mock('../src/api')

function button(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

test('ArtifactTab 加载已有产物', async () => {
  api.getArtifact.mockResolvedValue({ content: '# 已有报告' })
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'analysis', generateLabel: '生成拆解报告' },
  })
  await flushPromises()
  expect(api.getArtifact).toHaveBeenCalledWith('deadbeef', 'analysis')
  expect(wrapper.text()).toContain('已有报告')
})

test('ArtifactTab kind=analysis 生成调 stage2Generate 并可编辑保存', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage2Generate.mockResolvedValue({ content: '# 报告' })
  api.putArtifact.mockResolvedValue({ ok: true })
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'analysis', generateLabel: '生成拆解报告' },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('尚未生成')
  await button(wrapper, '生成拆解报告').trigger('click')
  await flushPromises()
  expect(api.stage2Generate).toHaveBeenCalledWith('deadbeef')
  expect(wrapper.text()).toContain('报告')
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('textarea').setValue('# 修改后')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putArtifact).toHaveBeenCalledWith('deadbeef', 'analysis', '# 修改后')
})

test('ArtifactTab kind=outline 生成调 stage4Generate', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage4Generate.mockResolvedValue({ content: '# 大纲' })
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'outline', generateLabel: '生成逐集大纲' },
  })
  await flushPromises()
  await button(wrapper, '生成逐集大纲').trigger('click')
  await flushPromises()
  expect(api.stage4Generate).toHaveBeenCalledWith('deadbeef')
  expect(wrapper.text()).toContain('大纲')
})

test('ArtifactTab 生成失败展示错误', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage2Generate.mockRejectedValue(new Error('还没有已完成的扒剧剧本'))
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'analysis', generateLabel: '生成拆解报告' },
  })
  await flushPromises()
  await button(wrapper, '生成拆解报告').trigger('click')
  await flushPromises()
  expect(wrapper.find('.error').text()).toContain('还没有已完成的扒剧剧本')
})

test('Stage3 AI 建议题材仅展示', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage3Suggest.mockResolvedValue({ content: '1. 都市修仙\n2. 民国悬疑' })
  const wrapper = mount(Stage3Settings, { props: { pid: 'deadbeef' } })
  await flushPromises()
  await button(wrapper, 'AI 建议新题材').trigger('click')
  await flushPromises()
  expect(api.stage3Suggest).toHaveBeenCalledWith('deadbeef')
  expect(wrapper.text()).toContain('都市修仙')
  expect(api.putArtifact).not.toHaveBeenCalled()
})

test('Stage3 AI 完善设定并可编辑保存', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage3Refine.mockResolvedValue({ content: '# 新剧设定' })
  api.putArtifact.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage3Settings, { props: { pid: 'deadbeef' } })
  await flushPromises()
  await wrapper.find('textarea').setValue('题材：都市修仙')
  await button(wrapper, 'AI 完善设定').trigger('click')
  await flushPromises()
  expect(api.stage3Refine).toHaveBeenCalledWith('deadbeef', '题材：都市修仙')
  expect(wrapper.text()).toContain('新剧设定')
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('.editor-pane textarea').setValue('# 改过的设定')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putArtifact).toHaveBeenCalledWith('deadbeef', 'settings', '# 改过的设定')
})
