import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../src/api'

function mockFetch(body, ok = true, status = 200) {
  const res = {
    ok,
    status,
    statusText: 'HTTP ' + status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  }
  const fn = vi.fn(async () => res)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

test('createProject 发送 POST JSON', async () => {
  const fn = mockFetch({ id: 'abc12345' })
  const out = await api.createProject('测试', 'D:/videos')
  expect(fn.mock.calls[0][0]).toBe('/api/projects')
  expect(fn.mock.calls[0][1].method).toBe('POST')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ name: '测试', video_dir: 'D:/videos' })
  expect(out.id).toBe('abc12345')
})

test('getProject 发送 GET', async () => {
  const fn = mockFetch({ id: 'deadbeef', episodes: [] })
  await api.getProject('deadbeef')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef')
  expect(fn.mock.calls[0][1].method).toBe('GET')
})

test('非 2xx 抛出 detail 错误', async () => {
  mockFetch({ detail: '项目不存在' }, false, 404)
  await expect(api.getProject('deadbeef')).rejects.toThrow('项目不存在')
})

test('updateMapping 发送 episodes 数组', async () => {
  const fn = mockFetch({ ok: true })
  await api.updateMapping('deadbeef', [{ episode: 1, file: 'a.mp4' }])
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/episodes-mapping')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ episodes: [{ episode: 1, file: 'a.mp4' }] })
})

test('stage1Start 默认 episodes 为 null', async () => {
  const fn = mockFetch({ started: [1] })
  await api.stage1Start('deadbeef')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/stage1/start')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ episodes: null })
})

test('stage3Refine 发送 draft', async () => {
  const fn = mockFetch({ content: '设定' })
  await api.stage3Refine('deadbeef', '草稿')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/stage3/refine')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ draft: '草稿' })
})

test('stage5Start 传 episodes 与 extra', async () => {
  const fn = mockFetch({ started: [1, 2] })
  await api.stage5Start('deadbeef', [1, 2], '台词更口语化')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/stage5/start')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ episodes: [1, 2], extra: '台词更口语化' })
})

test('putArtifact 与 getNewScript 路径正确', async () => {
  let fn = mockFetch({ ok: true })
  await api.putArtifact('deadbeef', 'settings', '内容')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/artifacts/settings')
  fn = mockFetch({ content: '剧本' })
  await api.getNewScript('deadbeef', 3)
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/scripts/3')
})

test('exportUrl 拼接 which 参数', () => {
  expect(api.exportUrl('deadbeef', 'new')).toBe('/api/projects/deadbeef/export?which=new')
  expect(api.exportUrl('deadbeef', 'original')).toBe('/api/projects/deadbeef/export?which=original')
})
