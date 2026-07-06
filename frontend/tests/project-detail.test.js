import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import * as sse from '../src/sse'
import ProjectDetail from '../src/views/ProjectDetail.vue'

vi.mock('../src/api')
vi.mock('../src/sse')

const project = {
  id: 'deadbeef', name: '霸总剧', video_dir: 'D:/v', running: false, episodes: [],
}

test('加载项目并渲染五个页签', async () => {
  api.getProject.mockResolvedValue(project)
  sse.subscribeEvents.mockReturnValue(vi.fn())
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(wrapper.text()).toContain('霸总剧')
  expect(wrapper.findAll('.tabs button .tab-label').map((b) => b.text())).toEqual([
    '扒剧', '拆解报告', '新剧设定', '大纲', '新剧剧本',
  ])
  // 无产物时序号圆圈显示 ①-⑤（未完成，不显示 ✓）
  expect(wrapper.findAll('.tabs button .step-num').map((s) => s.text())).toEqual([
    '①', '②', '③', '④', '⑤',
  ])
})

test('SSE 事件触发刷新，卸载时取消订阅', async () => {
  api.getProject.mockResolvedValue(project)
  let handler
  const stop = vi.fn()
  sse.subscribeEvents.mockImplementation((pid, cb) => {
    handler = cb
    return stop
  })
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(api.getProject).toHaveBeenCalledTimes(1)
  await handler({ type: 'item_done', item: 1, ok: true })
  expect(api.getProject).toHaveBeenCalledTimes(2)
  wrapper.unmount()
  expect(stop).toHaveBeenCalled()
})

test('加载失败展示错误信息', async () => {
  api.getProject.mockRejectedValue(new Error('后端未启动'))
  sse.subscribeEvents.mockReturnValue(vi.fn())
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(wrapper.find('.error').text()).toContain('后端未启动')
  expect(wrapper.text()).not.toContain('加载中')
})

test('切换页签渲染对应组件', async () => {
  api.getProject.mockResolvedValue(project)
  sse.subscribeEvents.mockReturnValue(vi.fn())
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(wrapper.findComponent({ name: 'Stage1Extract' }).exists()).toBe(true)
  await wrapper.findAll('.tabs button')[1].trigger('click')
  expect(wrapper.findComponent({ name: 'ArtifactTab' }).exists()).toBe(true)
})
