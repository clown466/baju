import { afterEach, expect, test, vi } from 'vitest'
import { subscribeEvents } from '../src/sse'

class FakeEventSource {
  static last = null
  constructor(url) {
    this.url = url
    this.onmessage = null
    this.closed = false
    FakeEventSource.last = this
  }
  close() { this.closed = true }
}

afterEach(() => vi.unstubAllGlobals())

test('订阅、解析事件、取消关闭', () => {
  vi.stubGlobal('EventSource', FakeEventSource)
  const events = []
  const stop = subscribeEvents('deadbeef', (e) => events.push(e))
  const es = FakeEventSource.last
  expect(es.url).toBe('/api/projects/deadbeef/events')
  es.onmessage({ data: '{"type":"item_done","item":3,"ok":true}' })
  es.onmessage({ data: '{"type":"batch_done"}' })
  es.onmessage({ data: 'not-json' })
  expect(events).toEqual([
    { type: 'item_done', item: 3, ok: true },
    { type: 'batch_done' },
  ])
  stop()
  expect(es.closed).toBe(true)
})
