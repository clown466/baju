export function subscribeEvents(pid, onEvent) {
  const es = new EventSource(`/api/projects/${pid}/events`)
  es.onmessage = (e) => {
    if (!e.data) return
    let event
    try {
      event = JSON.parse(e.data)
    } catch {
      return
    }
    onEvent(event)
  }
  return () => es.close()
}
