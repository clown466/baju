import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from '../src/api'
import { useConfirm } from '../src/composables/useConfirm'
import Stage5Scripts from '../src/tabs/Stage5Scripts.vue'

vi.mock('../src/api')

beforeEach(() => {
  useConfirm().settle(false) // 清理确认框单例状态
})

/* 点击目标按钮后在确认框上点「确定/取消」（组件未挂载 ConfirmDialog，直接驱动单例） */
async function answerConfirm(ok) {
  await flushPromises()
  expect(useConfirm().state.visible).toBe(true)
  useConfirm().settle(ok)
  await flushPromises()
}

function makeProject(running = false) {
  return {
    id: 'deadbeef', name: '霸总剧', video_dir: 'D:/v', running,
    episodes: [
      { episode: 1, file: '第01集.mp4', status: 'done', error: '' },
      { episode: 2, file: '第02集.mp4', status: 'done', error: '' },
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

test('批量生成带附加指令', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage5Start.mockResolvedValue({ started: [1, 2] })
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.find('textarea').setValue('台词更口语化')
  await button(wrapper, '批量生成全部').trigger('click')
  await answerConfirm(true)
  expect(api.stage5Start).toHaveBeenCalledWith('deadbeef', null, '台词更口语化')
})

test('批量生成先弹确认，取消则不调用接口', async () => {
  api.exportUrl.mockReturnValue('#')
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await button(wrapper, '批量生成全部').trigger('click')
  expect(useConfirm().state.message).toContain('批量生成全部剧集')
  await answerConfirm(false)
  expect(api.stage5Start).not.toHaveBeenCalled()
})

test('运行中禁用生成并可取消', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage1Cancel.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage5Scripts, opts(makeProject(true)))
  expect(button(wrapper, '批量生成全部').attributes('disabled')).toBeDefined()
  await button(wrapper, '取消').trigger('click')
  await flushPromises()
  expect(api.stage1Cancel).toHaveBeenCalledWith('deadbeef')
})

test('单集生成并展示结果', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage5Generate.mockResolvedValue({ content: '1-1 夜 内 修炼室' })
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.find('textarea').setValue('更热血')
  await wrapper.findAll('button').filter((b) => b.text() === '生成/重生成')[1].trigger('click')
  expect(useConfirm().state.message).toContain('第 2 集')
  await answerConfirm(true)
  expect(api.stage5Generate).toHaveBeenCalledWith('deadbeef', 2, '更热血')
  expect(wrapper.text()).toContain('新剧第 2 集')
  expect(wrapper.text()).toContain('1-1 夜 内 修炼室')
})

test('查看并保存已有新剧本', async () => {
  api.exportUrl.mockReturnValue('#')
  api.getNewScript.mockResolvedValue({ content: '旧内容' })
  api.putNewScript.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.findAll('button').filter((b) => b.text() === '查看')[0].trigger('click')
  await flushPromises()
  expect(api.getNewScript).toHaveBeenCalledWith('deadbeef', 1)
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('.editor-pane textarea').setValue('改后内容')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putNewScript).toHaveBeenCalledWith('deadbeef', 1, '改后内容')
})

test('查看不存在的新剧本展示错误', async () => {
  api.exportUrl.mockReturnValue('#')
  api.getNewScript.mockRejectedValue(new Error('该集新剧本不存在'))
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.findAll('button').filter((b) => b.text() === '查看')[0].trigger('click')
  await flushPromises()
  expect(wrapper.find('.error').text()).toContain('该集新剧本不存在')
})
