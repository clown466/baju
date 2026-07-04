import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import Stage1Extract from '../src/tabs/Stage1Extract.vue'

vi.mock('../src/api')

function makeProject(running = false) {
  return {
    id: 'deadbeef', name: '霸总剧', video_dir: 'D:/v', running,
    episodes: [
      { episode: 1, file: '第01集.mp4', status: 'done', error: '' },
      { episode: 2, file: '第02集.mp4', status: 'failed', error: '上传超时' },
      { episode: 3, file: '第03集.mp4', status: 'pending', error: '' },
    ],
  }
}

function opts(project) {
  return {
    props: { pid: 'deadbeef', project },
    global: { provide: { refresh: vi.fn() } },
  }
}

function button(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

test('展示分集状态、错误与完成计数', () => {
  api.exportUrl.mockReturnValue('#')
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  expect(wrapper.text()).toContain('完成 1 / 3')
  expect(wrapper.text()).toContain('第02集.mp4')
  expect(wrapper.text()).toContain('上传超时')
  expect(wrapper.find('.status-done').exists()).toBe(true)
})

test('开始扒剧与失败重跑', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage1Start.mockResolvedValue({ started: [] })
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  await button(wrapper, '开始扒剧').trigger('click')
  await flushPromises()
  expect(api.stage1Start).toHaveBeenCalledWith('deadbeef')
  await button(wrapper, '重跑').trigger('click')
  await flushPromises()
  expect(api.stage1Start).toHaveBeenCalledWith('deadbeef', [2])
})

test('运行中显示取消按钮', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage1Cancel.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage1Extract, opts(makeProject(true)))
  expect(button(wrapper, '开始扒剧')).toBeUndefined()
  await button(wrapper, '取消').trigger('click')
  await flushPromises()
  expect(api.stage1Cancel).toHaveBeenCalledWith('deadbeef')
})

test('编辑并保存集数映射', async () => {
  api.exportUrl.mockReturnValue('#')
  api.updateMapping.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  await button(wrapper, '调整集数对应').trigger('click')
  await wrapper.findAll('td input')[0].setValue(9)
  await button(wrapper, '保存集数对应').trigger('click')
  await flushPromises()
  expect(api.updateMapping).toHaveBeenCalledWith('deadbeef', [
    { episode: 9, file: '第01集.mp4' },
    { episode: 2, file: '第02集.mp4' },
    { episode: 3, file: '第03集.mp4' },
  ])
})

test('查看并保存单集剧本', async () => {
  api.exportUrl.mockReturnValue('#')
  api.getEpisodeScript.mockResolvedValue({ content: '1-1 日 内 客厅' })
  api.putEpisodeScript.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  await button(wrapper, '查看/编辑').trigger('click')
  await flushPromises()
  expect(api.getEpisodeScript).toHaveBeenCalledWith('deadbeef', 1)
  expect(wrapper.text()).toContain('第 1 集原剧剧本')
  expect(wrapper.text()).toContain('1-1 日 内 客厅')
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('.editor-pane textarea').setValue('1-1 夜 外 天台')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putEpisodeScript).toHaveBeenCalledWith('deadbeef', 1, '1-1 夜 外 天台')
})
