import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import * as sse from '../src/sse'
import Skeleton from '../src/components/Skeleton.vue'
import ArtifactTab from '../src/tabs/ArtifactTab.vue'
import ProjectDetail from '../src/views/ProjectDetail.vue'
import ProjectList from '../src/views/ProjectList.vue'

vi.mock('../src/api')
vi.mock('../src/sse')

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

test('Skeleton 渲染若干灰块', () => {
  const wrapper = mount(Skeleton, { props: { blocks: 4 } })
  expect(wrapper.findAll('.skeleton-block').length).toBe(4)
})

test('ProjectList 加载中显示骨架屏，返回后消失', async () => {
  let resolve
  api.listProjects.mockReturnValue(new Promise((r) => { resolve = r }))
  const wrapper = mount(ProjectList, { global: { stubs } })
  expect(wrapper.findComponent(Skeleton).exists()).toBe(true)
  resolve([{ id: 'deadbeef', name: '霸总剧', episodes: [{}] }])
  await flushPromises()
  expect(wrapper.findComponent(Skeleton).exists()).toBe(false)
  expect(wrapper.text()).toContain('霸总剧')
})

test('ProjectList 无项目时显示图形化空状态（保留「暂无项目」文案）', async () => {
  api.listProjects.mockResolvedValue([])
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  const empty = wrapper.find('.empty-state')
  expect(empty.exists()).toBe(true)
  expect(empty.text()).toContain('🎬')
  expect(empty.text()).toContain('还没有项目')
  expect(empty.text()).toContain('暂无项目')
})

test('ProjectList 有项目时不显示空状态', async () => {
  api.listProjects.mockResolvedValue([{ id: 'deadbeef', name: '霸总剧', episodes: [] }])
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  expect(wrapper.find('.empty-state').exists()).toBe(false)
})

test('ProjectDetail 加载中显示骨架屏而非文字', async () => {
  api.getProject.mockReturnValue(new Promise(() => {}))
  sse.subscribeEvents.mockReturnValue(vi.fn())
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(wrapper.text()).not.toContain('加载中')
  expect(wrapper.findComponent(Skeleton).exists()).toBe(true)
})

test('ArtifactTab 尚未生成用空状态样式包裹（保留文案）', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'analysis', generateLabel: '生成拆解报告' },
  })
  await flushPromises()
  const empty = wrapper.find('.empty-state')
  expect(empty.exists()).toBe(true)
  expect(empty.text()).toContain('尚未生成')
})
