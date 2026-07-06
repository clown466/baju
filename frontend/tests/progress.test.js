import { mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import ProgressBar from '../src/components/ProgressBar.vue'
import Stage1Extract from '../src/tabs/Stage1Extract.vue'
import Stage5Scripts from '../src/tabs/Stage5Scripts.vue'

vi.mock('../src/api')

test('确定进度：done/total → fill 宽度百分比与文本', () => {
  const wrapper = mount(ProgressBar, { props: { done: 2, total: 5 } })
  expect(wrapper.find('.progress-bar').exists()).toBe(true)
  expect(wrapper.find('.progress-fill').attributes('style')).toContain('width: 40%')
  expect(wrapper.text()).toContain('2/5')
})

test('indeterminate 模式：无数字，有 .indeterminate class', () => {
  const wrapper = mount(ProgressBar, { props: { indeterminate: true } })
  expect(wrapper.find('.progress-bar').classes()).toContain('indeterminate')
  expect(wrapper.text()).not.toMatch(/\d+\/\d+/)
})

test('total 为 0 时 fill 宽度为 0%', () => {
  const wrapper = mount(ProgressBar, { props: { done: 0, total: 0 } })
  expect(wrapper.find('.progress-fill').attributes('style')).toContain('width: 0%')
})

function project(running) {
  return {
    id: 'deadbeef', name: '霸总剧', video_dir: 'D:/v', running,
    episodes: [
      { episode: 1, file: 'a.mp4', status: 'done', error: '' },
      { episode: 2, file: 'b.mp4', status: 'analyzing', error: '' },
      { episode: 3, file: 'c.mp4', status: 'pending', error: '' },
    ],
  }
}

function opts(p) {
  return { props: { pid: 'deadbeef', project: p }, global: { provide: { refresh: vi.fn() } } }
}

test('Stage1 运行中显示确定进度条 1/3', () => {
  api.exportUrl.mockReturnValue('#')
  const wrapper = mount(Stage1Extract, opts(project(true)))
  const bar = wrapper.find('.progress-bar')
  expect(bar.exists()).toBe(true)
  expect(wrapper.find('.progress-fill').attributes('style')).toContain('width: 33')
  expect(bar.text()).toContain('1/3')
})

test('Stage1 未运行不显示进度条', () => {
  api.exportUrl.mockReturnValue('#')
  const wrapper = mount(Stage1Extract, opts(project(false)))
  expect(wrapper.find('.progress-bar').exists()).toBe(false)
})

test('Stage5 运行中显示不定进度条', () => {
  api.exportUrl.mockReturnValue('#')
  const wrapper = mount(Stage5Scripts, opts(project(true)))
  const bar = wrapper.find('.progress-bar')
  expect(bar.exists()).toBe(true)
  expect(bar.classes()).toContain('indeterminate')
})
