import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import Settings from '../src/views/Settings.vue'
import * as api from '../src/api'

vi.mock('../src/api')

const SETTINGS = {
  gemini: {
    api_key: 'gk', model: 'gemini-2.5-pro',
    base_url: 'https://proxy.example.com', upload: 'inline',
  },
  text_llm: {
    provider: 'lemon',
    providers: {
      lemon: { base_url: 'https://l/v1', api_key: 'sk-1', model: 'm1' },
    },
  },
}

function clone(x) { return JSON.parse(JSON.stringify(x)) }

describe('Settings', () => {
  it('加载并展示当前配置', async () => {
    api.getSettings.mockResolvedValue(clone(SETTINGS))
    const wrapper = mount(Settings, { global: { stubs: ['router-link'] } })
    await flushPromises()
    expect(wrapper.text()).toContain('视频识别')
    expect(wrapper.text()).toContain('文本生成')
    const inputs = wrapper.findAll('input')
    expect(inputs.some((i) => i.element.value === 'gk')).toBe(true)
    expect(inputs.some((i) => i.element.value === 'https://l/v1')).toBe(true)
  })

  it('修改后保存提交新配置', async () => {
    api.getSettings.mockResolvedValue(clone(SETTINGS))
    api.putSettings.mockResolvedValue(clone(SETTINGS))
    const wrapper = mount(Settings, { global: { stubs: ['router-link'] } })
    await flushPromises()
    const keyInput = wrapper.findAll('input').find((i) => i.element.value === 'gk')
    await keyInput.setValue('new-key')
    await wrapper.findAll('button').find((b) => b.text() === '保存设置').trigger('click')
    await flushPromises()
    expect(api.putSettings).toHaveBeenCalledTimes(1)
    const payload = api.putSettings.mock.calls[0][0]
    expect(payload.gemini.api_key).toBe('new-key')
    expect(payload.text_llm.provider).toBe('lemon')
    expect(wrapper.text()).toContain('已保存')
  })

  it('保存失败展示后端错误', async () => {
    api.getSettings.mockResolvedValue(clone(SETTINGS))
    api.putSettings.mockRejectedValue(new Error('配置无效：xx'))
    const wrapper = mount(Settings, { global: { stubs: ['router-link'] } })
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === '保存设置').trigger('click')
    await flushPromises()
    expect(wrapper.find('.error').text()).toContain('配置无效')
  })

  it('新增服务商并可切换', async () => {
    api.getSettings.mockResolvedValue(clone(SETTINGS))
    const wrapper = mount(Settings, { global: { stubs: ['router-link'] } })
    await flushPromises()
    await wrapper.find('input.new-provider').setValue('deepseek')
    await wrapper.findAll('button').find((b) => b.text() === '新增服务商').trigger('click')
    expect(wrapper.text()).toContain('deepseek')
    const select = wrapper.find('select.provider-select')
    expect(select.findAll('option').map((o) => o.element.value)).toContain('deepseek')
  })
})
