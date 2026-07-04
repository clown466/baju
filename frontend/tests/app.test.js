import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import App from '../src/App.vue'

test('渲染顶栏标题', () => {
  const wrapper = mount(App, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' }, RouterView: true } },
  })
  expect(wrapper.text()).toContain('短剧扒剧与仿写')
})
