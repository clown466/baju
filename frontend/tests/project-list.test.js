import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import ProjectList from '../src/views/ProjectList.vue'

vi.mock('../src/api')

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

test('加载并展示项目列表', async () => {
  api.listProjects.mockResolvedValue([
    { id: 'deadbeef', name: '霸总剧', episodes: [{}, {}] },
  ])
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  expect(wrapper.text()).toContain('霸总剧')
  expect(wrapper.text()).toContain('2 集')
})

test('创建项目后刷新列表', async () => {
  api.listProjects.mockResolvedValue([])
  api.createProject.mockResolvedValue({ id: 'deadbeef' })
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  await wrapper.findAll('input')[0].setValue('新剧')
  await wrapper.findAll('input')[1].setValue('D:/videos')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(api.createProject).toHaveBeenCalledWith('新剧', 'D:/videos')
  expect(api.listProjects).toHaveBeenCalledTimes(2)
})

test('创建失败展示错误', async () => {
  api.listProjects.mockResolvedValue([])
  api.createProject.mockRejectedValue(new Error('目录不存在'))
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  await wrapper.findAll('input')[0].setValue('新剧')
  await wrapper.findAll('input')[1].setValue('Z:/nope')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(wrapper.find('.error').text()).toContain('目录不存在')
})
